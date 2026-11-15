# AI-assisted code: written with Anthropic Claude under the direction of the GeoElectronic team, reviewed and tested by the team.
"""Nubosidad diurna diaria sobre el Tolima (MODIS Terra Cloud Fraction Day, NASA GIBS) -> data/nubes.json.
Uso: python pipeline/nubes.py CARPETA_CON_cf_cmap.xml data/nubes.json
(cf_cmap.xml = https://gibs.earthdata.nasa.gov/colormaps/v1.3/MODIS_Cloud_Fraction.xml)"""
import json,math,io,re,sys,datetime as dt,urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
T=sys.argv[1];OUT=sys.argv[2]
cm={}
for m in re.finditer(r'rgb="(\d+),(\d+),(\d+)"[^>]*value="(\d+)"([^>]*)',open(T+'/cf_cmap.xml').read()):
    if 'nodata' in m.group(5):continue
    cm[(int(m.group(1)),int(m.group(2)),int(m.group(3)))]=int(m.group(4))
def px(lon,lat):
    x=((lon+180)/360*64-18)*256
    s=math.sin(math.radians(lat));y=((0.5-math.log((1+s)/(1-s))/(4*math.pi))*64-31)*256
    return int(x),int(y)
x0,y0=px(-76.1,5.32);x1,y1=px(-74.47,2.87)
def one(d):
    u=f'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_Cloud_Fraction_Day/default/{d}/GoogleMapsCompatible_Level6/6/31/18.png'
    for k in range(3):
        try:
            b=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'hackathon-fire-calendar/1.0'}),timeout=30).read()
            im=Image.open(io.BytesIO(b)).convert('RGBA');vals=[]
            for yy in range(y0,y1+1):
                for xx in range(x0,x1+1):
                    r,g,bb,a=im.getpixel((xx,yy))
                    if a==0:continue
                    v=cm.get((r,g,bb))
                    if v is not None:vals.append(v)
            return d,(round(sum(vals)/len(vals)) if len(vals)>20 else None)
        except Exception as e:
            if '404' in str(e):return d,None
    return d,None
days=[]
d=dt.date(2000,2,24)
while d<=dt.date(2025,12,31):days.append(d.isoformat());d+=dt.timedelta(1)
res={}
with ThreadPoolExecutor(16) as ex:
    for i,(d,v) in enumerate(ex.map(one,days)):
        res[d]=v
        if i%1000==0:print(i,d,v,flush=True)
base=dt.date(2000,1,1);arr=[-1]*((dt.date(2025,12,31)-base).days+1)
for d,v in res.items():
    if v is not None:arr[(dt.date.fromisoformat(d)-base).days]=v
json.dump({'fuente':'NASA GIBS, MODIS_Terra_Cloud_Fraction_Day (MOD08), promedio sobre el Tolima','inicio':'2000-01-01','pct':arr},open(OUT,'w'),separators=(',',':'))
ok=[v for v in arr if v>=0];print('dias con dato',len(ok),'<30%',sum(v<30 for v in ok),'<50%',sum(v<50 for v in ok))
