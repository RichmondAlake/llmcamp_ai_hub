/* Inline SVG works offline and needs no Mermaid runtime. */
const diagramIcons = {
 user:'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M4 22v-3c0-6 16-6 16 0v3',
 document:'M5 2h10l5 5v15H5z M15 2v6h5 M8 12h9 M8 16h9',
 database:'M3 5c0-5 18-5 18 0s-18 5-18 0v14c0 5 18 5 18 0V5 M3 12c0 5 18 5 18 0',
 vector:'M4 4h5v5H4z M15 4h5v5h-5z M4 15h5v5H4z M15 15h5v5h-5z',
 search:'M16 16l7 7 M17 10a7 7 0 1 0-14 0 7 7 0 0 0 14 0',
 code:'M8 5l-6 7 6 7 M16 5l6 7-6 7 M14 3l-4 18',
 decision:'M12 1l11 11-11 11L1 12z M7 12l3 3 7-7',
 model:'M4 5h16v14H4z M8 1v4 M16 1v4 M8 19v4 M16 19v4 M1 9h3 M1 15h3 M20 9h3 M20 15h3 M9 9h6v6H9z',
 review:'M4 3h16v19H4z M7 8l2 2 4-4 M7 16l2 2 4-4 M15 8h3 M15 16h3',
};
function renderDiagram(spec,index) {
 const article=node('figure',undefined,'flow-figure');article.append(node('h3',spec.title));
 const h=75+Math.max(...spec.nodes.map(n=>n.y))*165+100;
 const s=svgEl('svg',{viewBox:`0 0 960 ${h}`,role:'img','aria-label':spec.title});
 s.append(svgEl('title',{},spec.title),svgEl('desc',{},spec.edges.map(e=>{
   const a=spec.nodes.find(n=>n.id===e.source),b=spec.nodes.find(n=>n.id===e.target);
   return `${a.title} → ${e.label} → ${b.title}`;
 }).join('. ')));
 const defs=svgEl('defs'),marker=svgEl('marker',{id:`arrow-${index}`,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});
 marker.append(svgEl('path',{d:'M0 0L10 5L0 10z',fill:'#71866e'}));defs.append(marker);s.append(defs);
 const pos=n=>({x:20+n.x*335,y:28+n.y*165});
 spec.edges.forEach(e=>{
   const a=pos(spec.nodes.find(n=>n.id===e.source)),b=pos(spec.nodes.find(n=>n.id===e.target));
   let x1=a.x+125,y1=a.y+45,x2=b.x+125,y2=b.y+45;
   if(a.y===b.y){const d=Math.sign(b.x-a.x);x1+=d*125;x2-=d*125;}
   else {const d=Math.sign(b.y-a.y);y1+=d*45;y2-=d*45;}
   s.append(svgEl('path',{d:`M${x1} ${y1}L${x2} ${y2}`,fill:'none',stroke:'#71866e','stroke-width':1.7,'marker-end':`url(#arrow-${index})`}));
   const x=(x1+x2)/2,y=(y1+y2)/2-(a.y===b.y?12:0),words=e.label.split(' '),split=Math.ceil(words.length/2);
   const lines=e.label.length>14?[words.slice(0,split).join(' '),words.slice(split).join(' ')]:[e.label];
   lines.forEach((line,i)=>label(s,x+(a.y===b.y?0:8),y+i*13,line,{'text-anchor':a.y===b.y?'middle':'start','font-size':10,'class':'flow-arrow-label'}));
 });
 spec.nodes.forEach(n=>{
   const {x,y}=pos(n),accent=n.icon==='decision';
   s.append(svgEl('rect',{x,y,width:250,height:90,rx:9,fill:accent?'#e1ecd7':'#fffef9',stroke:accent?'#90ab80':'#cbd1c1'}));
   const icon=svgEl('g',{transform:`translate(${x+16} ${y+18})`,fill:'none',stroke:accent?'#46693e':'#637260','stroke-width':1.6,'stroke-linecap':'round','stroke-linejoin':'round'});
   icon.append(svgEl('path',{d:diagramIcons[n.icon]||diagramIcons.document}));s.append(icon);
   label(s,x+51,y+32,n.title,{'font-size':13,'font-weight':650});label(s,x+16,y+65,n.detail,{'font-size':11});
 });
 const scroll=node('div',undefined,'flow-scroll');scroll.append(s);article.append(scroll,node('figcaption',spec.note));return article;
}
function renderGuides(lesson) {
 $('walkthrough').textContent=lesson.walkthrough;$('experiment-scope').textContent=lesson.scope;
 $('use-case-diagram').replaceChildren(renderDiagram(lesson.diagrams[0],0));
 $('reference-diagrams').replaceChildren(...lesson.diagrams.slice(1).map((spec,i)=>renderDiagram(spec,i+1)));
}
