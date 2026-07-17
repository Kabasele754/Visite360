from .base import BaseCollector,CollectorResult
class GoogleTrendsCollector(BaseCollector):
    provider='google_trends'
    def collect(self,start_date,end_date):
        try: from pytrends.request import TrendReq
        except ImportError as e: raise RuntimeError('Install pytrends to enable Google Trends') from e
        from apps.growth_ai.models import TrackedKeyword
        kws=list(TrackedKeyword.objects.filter(organization=self.connection.organization,is_active=True).values_list('keyword',flat=True)[:25])
        rows=[]; py=TrendReq(hl=self.config.get('hl','en-ZA'),tz=self.config.get('tz',120))
        for i in range(0,len(kws),5):
            batch=kws[i:i+5]; py.build_payload(batch,timeframe=f'{start_date} {end_date}',geo=self.config.get('geo','ZA')); df=py.interest_over_time()
            if df is None or df.empty: continue
            for idx,r in df.iterrows():
                for kw in batch: rows.append({'date':idx.date(),'dimensions':{'keyword':kw,'geo':self.config.get('geo','ZA')},'metrics':{'interest':int(r.get(kw,0))}})
        return CollectorResult(len(rows),self.save_rows(rows),{'keywords':len(kws)})
