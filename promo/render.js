// Renders an animation page to PNG frames: node render.js <outDir> [fps] [page.html]
const {chromium}=require('playwright');
(async()=>{
  const out=process.argv[2], fps=+(process.argv[3]||30);
  const b=await chromium.launch();
  const pg=await b.newPage({viewport:{width:540,height:960},deviceScaleFactor:2});
  await pg.goto('file://'+__dirname+'/'+(process.argv[4]||'promo.html')); await pg.waitForFunction(()=>window.READY);
  const D=await pg.evaluate(()=>DURATION), N=Math.round(D*fps);
  for(let i=0;i<N;i++){
    await pg.evaluate(t=>render(t),i/fps);
    await pg.screenshot({path:`${out}/f${String(i).padStart(4,'0')}.png`});
  }
  await b.close(); console.log('frames',N);
})();
