// Renders overlay.html to transparent PNG frames: node render_overlay.js <outDir>
const {chromium}=require('playwright');const fs=require('fs'),path=require('path');
(async()=>{const out=process.argv[2];const b=await chromium.launch();
 const pg=await b.newPage({viewport:{width:540,height:960},deviceScaleFactor:2});
 pg.on('pageerror',e=>console.error('ERR',e.message));
 await pg.route('http://local/**',r=>{const f=path.join(__dirname,'..',decodeURIComponent(new URL(r.request().url()).pathname));
   r.fulfill({status:200,contentType:f.endsWith('.html')?'text/html':f.endsWith('.json')?'application/json':'font/woff2',body:fs.readFileSync(f)});});
 await pg.goto('http://local/blender/overlay.html');await pg.waitForFunction(()=>window.READY);
 const {D,F}=await pg.evaluate(()=>({D:DURATION,F:FPS}));const N=Math.round(D*F);
 for(let i=0;i<N;i++){await pg.evaluate(t=>render(t),i/F);await pg.screenshot({path:`${out}/o${String(i).padStart(4,'0')}.png`,omitBackground:true});}
 console.log('overlay frames',N);await b.close();})();
