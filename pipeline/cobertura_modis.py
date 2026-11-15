# AI-assisted code: written with Anthropic Claude under the direction of the GeoElectronic team, reviewed and tested by the team.
"""Mide en la imagen real MODIS Terra (NASA GIBS) de cada dia: % del Tolima con datos (sin franjas negras) y % de nubes.
Uso: python pipeline/cobertura_modis.py data/nubes.json"""
import json,math,io,sys,datetime as dt,urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
OUT=sys.argv[1]
Z=7
def tile(lon,lat):
    n=2**Z;x=(lon+180)/360*n;s=math.sin(math.radians(lat));y=(0.5-math.log((1+s)/(1-s))/(4*math.pi))*n
    return x,y
# Tolima bbox en coordenadas de tesela z7
xa,ya=tile(-76.1,5.32);xb,yb=tile(-74.47,2.87)
tiles=[(tx,ty) for tx in range(int(xa),int(xb)+1) for ty in range(int(ya),int(yb)+1)]
def one(d):
    cov=tot=cl=0
    for tx,ty in tiles:
        u=f'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/{d}/GoogleMapsCompatible_Level9/{Z}/{ty}/{tx}.jpg'
        im=None
        for k in range(3):
            try:im=Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'hackathon-fire-calendar/1.0'}),timeout=30).read())).convert('RGB');break
            except Exception as e:
                if '404' in str(e)or'400' in str(e):break
        if im is None:return d,None,None
        # recorte del bbox del Tolima dentro de esta tesela
        x0=max(0,int((xa-tx)*256));x1=min(256,int((xb-tx)*256));y0=max(0,int((ya-ty)*256));y1=min(256,int((yb-ty)*256))
        for yy in range(y0,y1,2):
            for xx in range(x0,x1,2):
                r,g,b=im.getpixel((xx,yy));tot+=1
                if r+g+b<25:continue
                cov+=1
                mx,mn=max(r,g,b),min(r,g,b)
                if (r+g+b)/3>165 and mx-mn<45:cl+=1
    if not tot:return d,None,None
    return d,round(100*cov/tot),(round(100*cl/cov) if cov else None)
days=[];d=dt.date(2000,2,24)
while d<=dt.date(2025,12,31):days.append(d.isoformat());d+=dt.timedelta(1)
base=dt.date(2000,1,1);N=(dt.date(2025,12,31)-base).days+1
cobA=[-1]*N;nubA=[-1]*N
with ThreadPoolExecutor(16) as ex:
    for i,(d,c,n) in enumerate(ex.map(one,days)):
        k=(dt.date.fromisoformat(d)-base).days
        if c is not None:cobA[k]=c
        if n is not None:nubA[k]=n
        if i%1500==0:print(i,d,c,n,flush=True)
old=json.load(open(OUT))
old['fuente']='Imagen real MODIS Terra (NASA GIBS, color verdadero): % del Tolima con datos y % de nubes blancas; mod08 = MODIS Cloud Fraction Day'
old['mod08']=old.get('mod08',old['pct']);old['cob']=cobA;old['pct']=nubA
json.dump(old,open(OUT,'w'),separators=(',',':'))
ok=[i for i in range(N) if cobA[i]>=90 and nubA[i]>=0]
print('dias con imagen completa',len(ok),'de ellos <30% nubes',sum(nubA[i]<30 for i in ok))
