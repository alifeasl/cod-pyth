// Renders an animation page to PNG frames.
//   node render.js <outDir> [fps] [page.html]
//   node render.js --snap <outDir> <page.html> t1 t2 ...   (single test frames, 1x)
// Pages are served from this folder through request interception (http://local/...),
// so ES modules work without running a web server.
const {chromium}=require('playwright');
const fs=require('fs'), path=require('path');
const TYPES={'.html':'text/html','.js':'text/javascript','.woff2':'font/woff2','.png':'image/png','.json':'application/json'};
(async()=>{
  const snap=process.argv[2]==='--snap';
  const a=snap?process.argv.slice(3):process.argv.slice(2);
  const out=a[0], page=snap?a[1]:(a[2]||'promo.html'), fps=snap?30:+(a[1]||30);
  const b=await chromium.launch({args:['--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
  const pg=await b.newPage({viewport:{width:540,height:960},deviceScaleFactor:snap?1:2});
  pg.on('pageerror',e=>console.error('PAGE ERROR',e.message));
  pg.on('console',m=>{if(m.type()==='error')console.error('CONSOLE',m.text());});
  await pg.route('http://local/**',r=>{
    const f=path.join(__dirname,decodeURIComponent(new URL(r.request().url()).pathname));
    if(!fs.existsSync(f))return r.fulfill({status:404,body:'nf'});
    r.fulfill({status:200,contentType:TYPES[path.extname(f)]||'application/octet-stream',body:fs.readFileSync(f)});
  });
  await pg.goto('http://local/'+page); await pg.waitForFunction(()=>window.READY,null,{timeout:60000});
  if(snap){
    for(const t of a.slice(2).map(Number)){await pg.evaluate(t=>render(t),t);await pg.screenshot({path:`${out}/t${t}.png`});}
  } else {
    const D=await pg.evaluate(()=>DURATION), N=Math.round(D*fps);
    const i0=+(process.env.START||0), i1=Math.min(N,+(process.env.END||N));
    for(let i=i0;i<i1;i++){
      await pg.evaluate(t=>render(t),i/fps);
      await pg.screenshot({path:`${out}/f${String(i).padStart(4,'0')}.png`});
      if(i%60===0)console.log('frame',i,'/',N);
    }
    console.log('frames',N);
  }
  await b.close();
})();
