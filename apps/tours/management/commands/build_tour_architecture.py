from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.tours.intelligence.dispatch import dispatch_tour_architecture
from apps.tours.intelligence.scene_architect import apply_link_proposal
from apps.tours.models import SceneLinkProposal, Tour


class Command(BaseCommand):
    help = (
        "Build the AI Tour Architect object catalogue, visual-quality review "
        "and Gemini-assisted scene-link proposals for a tour."
    )

    def add_arguments(self, parser):
        parser.add_argument("--tour", type=int, required=True, help="Tour primary key.")
        parser.add_argument(
            "--mode",
            choices=("auto", "sync", "thread", "celery"),
            default="auto",
            help="Execution mode. Local development normally uses thread; production uses Celery.",
        )
        parser.add_argument("--force", action="store_true", help="Create a new run even when one is active.")
        parser.add_argument(
            "--apply-safe",
            action="store_true",
            help="Apply high-confidence proposals after a synchronous run. Manual hotspots are never overwritten.",
        )
        parser.add_argument("--status-only", action="store_true", help="Print the latest run and proposal counts.")

    def handle(self, *args, **options):
        try:
            tour = Tour.objects.select_related("organization").get(pk=options["tour"])
        except Tour.DoesNotExist as exc:
            raise CommandError(f"Tour {options['tour']} was not found.") from exc

        if options["status_only"]:
            run = tour.architecture_runs.order_by("-created_at").first()
            if not run:
                self.stdout.write("No Tour Architect run exists for this tour.")
                return
            self.stdout.write(
                self.style.SUCCESS(
                    f"run={run.pk} status={run.status} stage={run.stage} "
                    f"scenes={run.scene_count} objects={run.object_count} "
                    f"proposals={run.proposal_count} applied={run.applied_count}"
                )
            )
            return

        mode = options["mode"]
        if options["apply_safe"] and mode not in {"sync"}:
            raise CommandError("--apply-safe requires --mode sync so proposals are available before the command exits.")

        dispatch = dispatch_tour_architecture(
            tour,
            force=options["force"],
            mode=mode,
        )
        run = dispatch.run
        run.refresh_from_db()
        self.stdout.write(
            self.style.SUCCESS(
                f"run={run.pk} created={dispatch.created} mode={dispatch.mode} "
                f"status={run.status} task={dispatch.task_id or '-'}"
            )
        )

        if not options["apply_safe"]:
            return

        threshold = float(getattr(settings, "TOUR_ARCHITECT_AUTO_APPLY_MIN_CONFIDENCE", 0.94))
        proposals = run.proposals.filter(
            status__in=[SceneLinkProposal.Status.SUGGESTED, SceneLinkProposal.Status.APPROVED],
            confidence__gte=threshold,
            source=SceneLinkProposal.Source.GEMINI,
        ).select_related("from_scene", "to_scene")

        applied = 0
        conflicts = 0
        for proposal in proposals:
            result = apply_link_proposal(proposal)
            if result.status == SceneLinkProposal.Status.APPLIED:
                applied += 1
            elif result.status == SceneLinkProposal.Status.CONFLICT:
                conflicts += 1

        run.refresh_from_db()
        self.stdout.write(
            self.style.SUCCESS(
                f"safe proposals applied={applied} conflicts={conflicts} "
                f"run_status={run.status}"
            )
        )
