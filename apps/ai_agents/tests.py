from django.test import SimpleTestCase

from apps.ai_agents.models import AgentDefinition
from apps.ai_agents.services.registry import DEFAULT_AGENT_SPECS


class DefaultAgentRegistryTests(SimpleTestCase):
    def test_all_enterprise_agent_types_are_provisioned(self):
        expected = {value for value, _label in AgentDefinition.AgentType.choices}
        self.assertEqual(set(DEFAULT_AGENT_SPECS), expected)
        self.assertEqual(len(DEFAULT_AGENT_SPECS), 9)

    def test_each_agent_has_a_prompt_and_tools(self):
        for spec in DEFAULT_AGENT_SPECS.values():
            self.assertTrue(spec["name"])
            self.assertTrue(spec["slug"])
            self.assertTrue(spec["prompt"])
            self.assertIsInstance(spec["tools"], list)
