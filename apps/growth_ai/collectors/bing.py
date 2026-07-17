from .base import BaseCollector,CollectorResult
from .http import request_json
class BingCollector(BaseCollector):
    provider='bing'
    def collect(self,start_date,end_date):
        key=self.credentials.get('api_key'); site=self.config.get('site_url')
        if not key or not site: raise ValueError('Bing requires api_key and config.site_url')
        data=request_json('https://ssl.bing.com/webmaster/api.svc/json/GetQueryStats',params={'apikey':key,'siteUrl':site})
        rows=[]
        for r in data.get('d',data.get('Data',[])) or []:
            ds=str(r.get('Date') or end_date)[:10]
            rows.append({'date':ds,'dimensions':{'query':r.get('Query','')},'metrics':{'clicks':r.get('Clicks',0),'impressions':r.get('Impressions',0),'ctr':r.get('Ctr',0),'position':r.get('AvgClickPosition',0)}})
        return CollectorResult(len(rows),self.save_rows(rows),{'site_url':site})
