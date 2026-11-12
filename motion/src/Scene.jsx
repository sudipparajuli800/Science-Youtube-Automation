import React from 'react';
import {AbsoluteFill, Img, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

const ink = '#edf3f0', muted = '#91a8b4', teal = '#8edae0';
const palette = [teal, '#d8bd83', '#b9d99e', '#aebce4', '#d9a9a0'];
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};

function Icon({kind='particle', x=0, y=0, size=100, color=teal}) {
  let art;
  if (kind === 'leaf') art = <><path d="M15 82Q0 8 86 10Q100 86 15 82Z"/><path d="M13 90L71 28M40 63L38 36M52 51L78 54"/></>;
  else if (kind === 'water') art = <><path d="M50 5C40 28 17 44 17 65A33 33 0 0 0 83 65C83 44 60 28 50 5Z"/><path d="M31 64Q31 80 46 81"/></>;
  else if (kind === 'ocean') art = <>{[25,50,75].map(v=><path key={v} d={`M5 ${v}Q17 ${v-17} 30 ${v}T55 ${v}T80 ${v}T105 ${v}`}/>)}</>;
  else if (kind === 'rock') art = <><path d="M8 65L23 19L67 8L92 40L82 87L31 93Z"/><path d="M23 19L48 48L92 40M48 48L31 93M48 48L67 8"/></>;
  else if (kind === 'sun') art = <><circle cx="50" cy="50" r="23"/>{Array.from({length:8},(_,i)=>{
    const a=i*Math.PI/4; return <line key={i} x1={50+34*Math.cos(a)} y1={50+34*Math.sin(a)} x2={50+46*Math.cos(a)} y2={50+46*Math.sin(a)}/>;
  })}</>;
  else if (kind === 'planet') art = <><circle cx="50" cy="50" r="38"/><path d="M15 35Q47 21 83 40M13 65Q57 82 86 60M50 12Q27 50 50 88"/></>;
  else if (kind === 'cell') art = <><ellipse cx="50" cy="50" rx="43" ry="34"/><ellipse cx="48" cy="49" rx="12" ry="10"/><path d="M21 40Q30 28 35 39M61 67Q78 71 79 58M63 28Q76 25 80 38"/></>;
  else if (kind === 'dna') art = <>{Array.from({length:7},(_,i)=>{
    const y=10+i*13, x=50+30*Math.sin(i*Math.PI/3);
    return <line key={i} x1={x} y1={y} x2={100-x} y2={y}/>;
  })}<path d="M50 5C100 25 0 70 50 95M50 5C0 25 100 70 50 95"/></>;
  else if (kind === 'atom') art = <><circle cx="50" cy="50" r="6"/>{[0,60,120].map(a=><ellipse key={a} cx="50" cy="50" rx="43" ry="17" transform={`rotate(${a} 50 50)`}/>)}</>;
  else if (kind === 'brain') art = <><path d="M49 15C33 0 15 14 19 30C0 39 6 59 17 61C8 81 32 96 49 82ZM51 15C67 0 85 14 81 30C100 39 94 59 83 61C92 81 68 96 51 82Z"/><path d="M22 31Q42 25 37 46M17 61Q37 54 34 73M78 31Q58 25 63 46M83 61Q63 54 66 73"/></>;
  else if (kind === 'magnet') art = <><path d="M15 15V55A35 35 0 0 0 85 55V15H65V55A15 15 0 0 1 35 55V15ZM15 35H35M65 35H85"/><path d="M40 9L45 2M60 9L55 2"/></>;
  else if (kind === 'telescope') art = <><path d="M10 32L73 9L86 43L23 66ZM35 62L51 81L74 61M51 81V96M51 81L27 96M51 81L77 96M86 43L96 39L83 5L73 9"/></>;
  else if (kind === 'microbe') art = <><ellipse cx="50" cy="50" rx="28" ry="35"/><path d="M50 5V15M50 85V95M10 50H22M78 50H90M20 20L29 29M80 80L71 71M80 20L71 29M20 80L29 71"/><circle cx="42" cy="39" r="5"/><circle cx="59" cy="57" r="7"/></>;
  else art = <>{[[23,29,8],[57,17,6],[79,42,9],[44,54,10],[16,72,5],[65,81,7]].map(([cx,cy,r],i)=><circle key={i} cx={cx} cy={cy} r={r}/>)}</>;
  return <g transform={`translate(${x-size/2},${y-size/2}) scale(${size/100})`} fill="none" stroke={color} strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round">{art}</g>;
}

function Label({text, x, y, size=38, anchor='middle', color=ink}) {
  const words=String(text).split(' '), lines=[];
  let line='';
  for (const word of words) {
    if ((line+' '+word).trim().length>19 && line) {lines.push(line); line=word;}
    else line=(line+' '+word).trim();
  }
  if(line)lines.push(line);
  return <text x={x} y={y} textAnchor={anchor} fontSize={size} fill={color} fontWeight="600">
    {lines.map((s,i)=><tspan key={i} x={x} dy={i===0?0:size*1.22}>{s}</tspan>)}
  </text>;
}

function Flow({spec, f, fps, frames, w, h, portrait, cues=[], centered=false}) {
  const nodes=spec.nodes, transport=spec.template==='transport';
  const positions=nodes.map((_,i)=>portrait?{x:centered?340:235,y:(i+.5)*h/nodes.length}:{x:(i+.5)*w/nodes.length,y:h*.43});
  return <>
    <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0 1L8 5L0 9" fill="none" stroke={teal} strokeWidth="1.5"/></marker></defs>
    {positions.slice(0,-1).map((p,i)=>{
      const end=positions[i+1];
      const p0=portrait?{x:p.x,y:p.y+90}:{x:p.x+82,y:p.y};
      const p1=portrait?{x:end.x,y:end.y-90}:{x:end.x-82,y:end.y};
      const start=cues[i] ?? i*frames*.12;
      const finish=Math.max(start+1,(cues[i+1] ?? (i*frames*.12+frames*.24))+10);
      const progress=interpolate(f,[start,finish],[0,1],clamp);
      return <g key={i}>
        <path d={`M${p0.x} ${p0.y}L${p1.x} ${p1.y}`} stroke={teal} strokeWidth="4.5" fill="none" opacity=".9" pathLength="1" strokeDasharray="1" strokeDashoffset={1-progress} markerEnd={progress>.98?'url(#arrow)':undefined}/>
        {transport && Array.from({length:8},(_,j)=>{
          const phase=((f/Math.max(1,frames*.45)+j/8)%1);
          return <circle key={j} cx={p0.x+(p1.x-p0.x)*phase} cy={p0.y+(p1.y-p0.y)*phase+(portrait?0:Math.sin(j*3)*12)} r={3+j%3} fill="#d8bd83" opacity={progress*.85}/>;
        })}
      </g>;
    })}
    {nodes.map((node,i)=>{
      const p=positions[i], entrance=spring({frame:Math.max(0,f-(cues[i] ?? i*frames*.11)),fps,config:{damping:200}});
      return <g key={i} opacity={entrance} transform={`translate(0,${(1-entrance)*22})`}>
        <circle cx={p.x} cy={p.y} r={portrait?80:66} fill="#192f3c" stroke={palette[i%5]} strokeOpacity=".3" strokeWidth="2"/>
        <Icon kind={node.icon} x={p.x} y={p.y} size={portrait?140:110} color={palette[i%5]}/>
        <Label text={node.label} x={portrait?p.x+150:p.x} y={portrait?p.y-8:p.y+130} anchor={portrait?'start':'middle'} size={portrait?60:42}/>

      </g>;
    })}
  </>;
}

function Bars({spec,f,frames,w,h,cues=[]}) {
  const max=Math.max(...spec.items.map(x=>x.value)), left=w*.34, width=w*.58;
  return <>{spec.items.map((item,i)=>{
    const y=(i+.5)*h/spec.items.length;
    const start=cues[i] ?? i*8;
    const p=interpolate(f,[start,Math.max(start+1,Math.min(frames-1,start+45))],[0,1],clamp);
    const eased=1-Math.pow(1-p,3), barWidth=width*(item.value/max)*eased;
    return <g key={i}>
      <Label text={item.label} x={left-30} y={y+7} anchor="end" size="32"/>
      <rect x={left} y={y-27} width={width} height="54" rx="8" fill="#1c3341"/>
      <rect x={left} y={y-27} width={barWidth} height="54" rx="8" fill={palette[i%5]}/>
      <text x={left} y={y-44} fontSize="32" fill={ink} opacity={p}>{item.value}{spec.unit?' '+spec.unit:''}</text>
    </g>;
  })}</>;
}

function Comparison({spec,f,frames,w,h,portrait}) {
  return <>{spec.nodes.map((node,i)=>{
    const x=portrait?w*.5:w*(i?.73:.27), y=portrait?h*(i?.73:.24):h*.45;
    const p=interpolate(f,[i*12,i*12+frames*.32],[0,1],clamp);
    return <g key={i} opacity={p} transform={`translate(0,${20*(1-p)})`}>
      <circle cx={x} cy={y} r="110" stroke={palette[i]} strokeOpacity=".35" fill="#192f3c" strokeWidth="2"/>
      <Icon kind={node.icon} x={x} y={y} size={145} color={palette[i]}/>
      <Label text={node.label} x={x} y={y+158} size="40"/>
    </g>;
  })}<text x={w/2} y={h/2} textAnchor="middle" fill={muted} fontSize="28">COMPARED</text></>;
}

function Orbit({spec,f,frames,w,h}) {
  const cx=w/2,cy=h/2,r=Math.min(w,h)*.35;
  const a=-Math.PI/2+(f/frames)*Math.PI*2;
  return <><circle cx={cx} cy={cy} r={r} stroke="#365568" strokeWidth="3" fill="none"/>
    <Icon kind={spec.nodes[0].icon} x={cx} y={cy} size="120" color="#d8bd83"/>
    <Label text={spec.nodes[0].label} x={cx} y={cy+105}/>
    <circle cx={cx+r*Math.cos(a)} cy={cy+r*Math.sin(a)} r="35" fill={teal}/>
    <Label text={spec.nodes[1].label} x={cx+r*Math.cos(a)} y={cy+r*Math.sin(a)-65} size="30"/>
  </>;
}

function Refraction({f,frames,w,h}) {
  const x=w*.52,y=h*.46;
  const progress=interpolate(f,[5,frames*.72],[0,1],clamp);
  const points=[[x-230,y-230],[x,y],[x+145,y+230]];
  return <><rect x="0" y={y} width={w} height={h-y} fill="#193f51" rx="15"/>
    <line x1="0" x2={w} y1={y} y2={y} stroke={teal} strokeWidth="2"/>
    <line x1={x} x2={x} y1="5" y2={h-5} stroke={muted} strokeDasharray="9 9" opacity=".6"/>
    <Label text="Air" x={90} y={y-45} anchor="start" color={muted}/>
    <Label text="Water" x={90} y={y+70} anchor="start" color={teal}/>
    <polyline points={points.map(p=>p.join(',')).join(' ')} fill="none" stroke="#d8bd83" strokeWidth="6" pathLength="1" strokeDasharray="1" strokeDashoffset={1-progress}/>
    {progress>.01 && <circle r="11" fill="white" cx={progress<.5?x-230+460*progress:x+290*(progress-.5)} cy={y-230+460*progress}/>}
  </>;
}

export function Scene({spec,frames,font,boldFont,image,cues=[],overlay=false,centered=false}) {
  const f=useCurrentFrame(), {width,height,fps}=useVideoConfig();
  const compact=width/height<1.4 && height/width<1.4;
  const portrait=height>width || compact, w=portrait?1000:1600,h=portrait?760:650;
  const common={spec,f,fps,frames,w,h,portrait,cues,centered};
  const photo=spec.template==='photo' && image;
  return <AbsoluteFill style={{background:overlay?'#000000':'#101c28',fontFamily:'Barlow',color:ink,overflow:'hidden'}}>
    <style>{`@font-face{font-family:Barlow;src:url(data:font/ttf;base64,${font})}@font-face{font-family:Barlow;src:url(data:font/ttf;base64,${boldFont});font-weight:700}`}</style>
    {overlay && <style>{`svg [fill="#192f3c"]{fill:none;stroke:none}svg text{paint-order:stroke;stroke:#000;stroke-width:2px;stroke-linejoin:round}svg{filter:drop-shadow(0 2px 3px #000)}`}</style>}
    {!overlay && <div style={{position:'absolute',top:compact?'3%':'6.5%',left:'8%',fontSize:compact?22:portrait?28:25,letterSpacing:4,color:teal}}>SCIENCE / EXPLAINED</div>}
    <div style={{position:'absolute',top:'10%',left:'8%',width:'84%',textAlign:centered?'center':'left',fontWeight:700,fontSize:compact?54:portrait?72:64,lineHeight:1.08,textShadow:overlay?'0 2px 6px #000':undefined,transform:`translateY(${interpolate(f,[0,16],[12,0],clamp)}px)`,opacity:interpolate(f,[0,12],[0,1],clamp)}}>{spec.title}</div>
    {photo?<div style={{position:'absolute',top:'26%',left:'8%',width:'84%',height:'38%',borderRadius:24,overflow:'hidden'}}>
      <Img src={image} style={{width:'100%',height:'100%',objectFit:'cover',transform:`scale(${1+.045*f/frames})`}}/>
      <div style={{position:'absolute',inset:0,background:'linear-gradient(transparent 35%,rgba(8,20,29,.9))'}}/>
      <div style={{position:'absolute',bottom:35,left:35,fontSize:portrait?36:32}}>{spec.nodes.map(n=>n.label).join(' · ')}</div>
    </div>:<svg viewBox={`0 0 ${w} ${h}`} style={{position:'absolute',left:'4%',width:'92%',top:portrait?'22%':'24%',height:portrait?'43%':'46%',overflow:'visible'}}>
      {['flow','transport'].includes(spec.template)&&<Flow {...common}/>}
      {spec.template==='bars'&&<Bars {...common}/>}
      {spec.template==='comparison'&&<Comparison {...common}/>}
      {spec.template==='orbit'&&<Orbit {...common}/>}
      {spec.template==='refraction'&&<Refraction {...common}/>}
    </svg>}
    <div style={{position:'absolute',top:portrait?'65.5%':'73%',left:'8%',width:'84%',textAlign:centered?'center':'left',fontSize:portrait?25:23,color:muted}}>{spec.template==='bars'?'Shared scale · zero baseline':photo?'Documentary image':'Schematic · not to scale'}</div>
  </AbsoluteFill>;
}
