const fs=require('fs'),path=require('path');const root=__dirname,base=path.join(root,'ksa_insurer_benchmark.Report/definition/pages/a0123456789012345678/visuals');
const lit=v=>({expr:{Literal:{Value:typeof v==='string'?`'${v}'`:typeof v==='number'?v+'D':String(v)}}}), color=v=>({solid:{color:lit(v)}});
const read=id=>JSON.parse(fs.readFileSync(path.join(base,id,'visual.json'),'utf8')),save=(id,v)=>fs.writeFileSync(path.join(base,id,'visual.json'),JSON.stringify(v,null,2));
const dax=`VAR one = HASONEVALUE ( dim_insurer[insurer_name] )
VAR cur = [Medical Loss Ratio]
VAR peers = FILTER ( ALL ( dim_insurer[insurer_name] ), NOT ISBLANK ( [Medical Loss Ratio] ) )
VAR rk = RANKX ( peers, [Medical Loss Ratio], cur, ASC, DENSE )
VAR n = COUNTROWS ( peers )
RETURN IF ( NOT one, "Select one insurer", IF ( ISBLANK ( cur ), BLANK (), rk & " of " & n ) )`;
fs.writeFileSync(path.join(root,'rank-card.dax'),dax);
const model=path.join(root,'ksa_insurer_benchmark.SemanticModel/definition/tables/dim_insurer.tmdl');let s=fs.readFileSync(model,'utf8');if(!s.includes("measure 'Rank Label (card)'"))s=s.replace(/\n\tcolumn /,`\n\tmeasure 'Rank Label (card)' =\n${dax.split('\n').map(l=>'\t\t\t'+l).join('\n')}\n\t\tdisplayFolder: 04 Change and rank\n\n\tcolumn `);fs.writeFileSync(model,s);
let id='b58e3254a9a9eaffc4a7',v=read(id);let p=v.visual.query.queryState.Values.projections[0];p.field.Measure.Property='Rank Label (card)';p.queryRef='dim_insurer.Rank Label (card)';p.nativeQueryRef='Rank Label (card)';v.visual.visualContainerObjects.title[0].properties.text=lit('Rank among peers');v.visual.objects.labels[0].properties.fontSize=lit(18);save(id,v);
id='dd58a17623f080307c24';v=read(id);v.visual.objects.labels[0].properties={...v.visual.objects.labels[0].properties,labelPosition:lit('OutsideEnd'),fontSize:lit(10),color:color('#0b0b0b')};v.visual.objects.valueAxis[0].properties.end=lit(1.6);let ref=v.visual.objects.y1AxisReferenceLine[0].properties;Object.assign(ref,{lineColor:color('#52514e'),style:lit('dashed'),strokeWidth:lit(1),dataLabelShow:lit(false)});save(id,v);
id='b8d1604f87dd2368f7f4';v=read(id);const names=['Bupa Arabia','Tawuniya','Medgulf','Al Rajhi Takaful','GIG (Saudi)','Malath','Walaa'],colors=['#2a78d6','#eb6834','#1baf7a','#30302e','#50504c','#6d6c66','#8a8983'],styles=['solid','solid','solid','dashed','dotted','dashDot','longDash'];
const selector=n=>({data:[{scopeId:{Comparison:{ComparisonKind:0,Left:{Column:{Expression:{SourceRef:{Entity:'dim_insurer'}},Property:'insurer_name'}},Right:{Literal:{Value:`'${n}'`}}}}}]});
v.visual.objects.dataPoint=names.map((n,i)=>({selector:selector(n),properties:{fill:color(colors[i])}}));
v.visual.objects.shapes=[{properties:{strokeWidth:lit(2),showMarker:lit(true),markerSize:lit(8)}},...names.map((n,i)=>({selector:selector(n),properties:{strokeWidth:lit(2),showMarker:lit(true),markerSize:lit(8),lineStyle:lit(styles[i])}}))];
v.visual.objects.lineStyles=names.map((n,i)=>({selector:selector(n),properties:{strokeWidth:lit(2),lineStyle:lit(styles[i]),showMarker:lit(true),markerSize:lit(8)}}));
ref=v.visual.objects.y1AxisReferenceLine[0].properties;Object.assign(ref,{lineColor:color('#52514e'),style:lit('dashed'),strokeWidth:lit(1),dataLabelShow:lit(false)});save(id,v);
console.log('Added card measure; modified only rank card, bar labels/reference, trend series.');
