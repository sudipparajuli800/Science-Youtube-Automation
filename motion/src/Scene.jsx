import {beatState} from './storytelling.mjs';
import React from 'react';
import {AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

const ink = '#edf3f0', muted = '#91a8b4', teal = '#8edae0';
const palette = [teal, '#d8bd83', '#b9d99e', '#aebce4', '#d9a9a0'];
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'};

function Icon({kind='particle', x=0, y=0, size=100, color=teal, reveal=1}) {
  let art;
  if (kind === 'leaf') art = <><path d="M15 82Q0 8 86 10Q100 86 15 82Z"/><path d="M13 90L71 28M40 63L38 36M52 51L78 54"/></>;
  else if (kind === 'water') art = <><path d="M50 5C40 28 17 44 17 65A33 33 0 0 0 83 65C83 44 60 28 50 5Z"/><path d="M31 64Q31 80 46 81"/></>;
  else if (kind === 'cloud' || kind === 'rain') art = <><path d="M22 62C2 62 2 35 21 32C18 9 56 2 63 24C88 13 104 52 82 62Z"/>{kind==='rain'&&[28,49,70].map(x=><path key={x} d={`M${x} 75L${x-6} 90`}/>)}</>;
  else if (kind === 'thermometer') art = <><path d="M37 64V18A13 13 0 0 1 63 18V64A23 23 0 1 1 37 64Z"/><path d="M50 30V74M69 23H83M69 39H78M69 55H83"/><circle cx="50" cy="79" r="7"/></>;
  else if (kind === 'microscope') art = <><path d="M23 9L48 4L65 47L40 56ZM18 80H80V94H12V80M52 24Q94 33 78 66Q73 77 55 80M19 64H58"/><circle cx="69" cy="34" r="6"/></>;
  else if (kind === 'heart') art = <><path d="M50 88C28 72 4 53 9 30C13 9 40 9 50 28C60 9 87 9 91 30C96 53 72 72 50 88Z"/><path d="M13 51H32L41 34L52 69L61 47H87"/></>;
  else if (kind === 'lightning') art = <path d="M56 4L16 56H44L36 96L86 40H56Z"/>;
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
  function trace(element) {
    if (!React.isValidElement(element)) return element;
    if (element.type === React.Fragment) return React.cloneElement(element, {}, React.Children.map(element.props.children, trace));
    return React.cloneElement(element, {pathLength: 1, strokeDasharray: 1, strokeDashoffset: 1-reveal});
  }
  return <g transform={`translate(${x-size/2},${y-size/2}) scale(${size/100})`} fill="none" stroke={color} strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round">{React.Children.map(art, trace)}</g>;
}

function Label({text, x, y, size=38, anchor='middle', color=ink, maxChars=19}) {
  const words=String(text).split(' '), lines=[];
  let line='';
  for (const word of words) {
    if ((line+' '+word).trim().length>maxChars && line) {lines.push(line); line=word;}
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
      const p=positions[i], beat=beatState(f,i,cues,frames,nodes.length,spec.treatment);
      return <g key={i} opacity={beat.opacity} transform={`translate(${beat.shift},0) rotate(${beat.rotation} ${p.x} ${p.y})`}>
        <circle cx={p.x} cy={p.y} r={portrait?80:66} fill="#192f3c" stroke={palette[i%5]} strokeOpacity=".3" strokeWidth="2"/>
        <Icon kind={node.icon} x={p.x} y={p.y} size={portrait?140:110} color={palette[i%5]} reveal={beat.draw}/>
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

function Comparison({spec,f,frames,w,h,portrait,cues=[]}) {
  return <>{spec.nodes.map((node,i)=>{
    const x=portrait?w*.5:w*(i?.73:.27), y=portrait?h*(i?.73:.24):h*.45;
    const beat=beatState(f,i,cues,frames,2,spec.treatment || 'focus'), p=beat.opacity;
    return <g key={i} opacity={p} transform={`translate(0,${20*(1-beat.visible)})`}>
      <circle cx={x} cy={y} r="110" stroke={palette[i]} strokeOpacity=".35" fill="#192f3c" strokeWidth="2"/>
      <Icon kind={node.icon} x={x} y={y} size={145} color={palette[i]} reveal={beat.draw}/>
      <Label text={node.label} x={x} y={y+158} size="40"/>
    </g>;
  })}<text x={w/2} y={h/2} textAnchor="middle" fill={muted} fontSize="28">COMPARED</text></>;
}

function Cycle({spec,f,frames,w,h,portrait,cues=[]}) {
  const nodes=spec.nodes, rx=w*.31, ry=h*.30, cy=h*.43;
  const positions=nodes.map((_,i)=>{const a=-Math.PI/2+2*Math.PI*i/nodes.length;
    return {x:w/2+rx*Math.cos(a),y:cy+ry*Math.sin(a)};});
  return <>
    <defs><marker id="cycle-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill={teal}/></marker></defs>
    {positions.map((p,i)=>{
      const next=positions[(i+1)%nodes.length], beat=beatState(f,i,cues,frames,nodes.length,spec.treatment);
      const dx=next.x-p.x,dy=next.y-p.y,len=Math.hypot(dx,dy), ux=dx/len,uy=dy/len;
      const from={x:p.x+ux*78,y:p.y+uy*78},to={x:next.x-ux*85,y:next.y-uy*85};
      return <g key={i}>
        <path d={`M${from.x} ${from.y}Q${(from.x+to.x)/2-uy*55} ${(from.y+to.y)/2+ux*55} ${to.x} ${to.y}`}
          fill="none" stroke={teal} strokeWidth="3.5" pathLength="1" strokeDasharray="1" strokeDashoffset={1-beat.visible}
          markerEnd={beat.visible===1?'url(#cycle-arrow)':undefined}/>
        <g opacity={beat.opacity} transform={`translate(${beat.shift},0) rotate(${beat.rotation} ${p.x} ${p.y})`}>
          <Icon kind={nodes[i].icon} x={p.x} y={p.y} size={portrait?140:120} color={palette[i]} reveal={beat.draw}/>
          <Label text={nodes[i].label} x={p.x} y={i===0?p.y-95:p.y+100} size={portrait?56:44} maxChars={16}/>
        </g>
      </g>;
    })}
  </>;
}

function Layers({spec,f,frames,w,h,portrait,cues=[]}) {
  const left=w*.08, band=w*(portrait?.36:.44), labelX=w*(portrait?.51:.6);
  return <>{spec.nodes.map((node,i)=>{
    const y=70+i*(h*.69/spec.nodes.length), beat=beatState(f,i,cues,frames,spec.nodes.length,spec.treatment || 'draw');
    return <g key={i} opacity={beat.opacity} transform={`translate(${beat.shift},0)`}>
      <path d={`M${left} ${y+20}Q${left+band*.45} ${y-20} ${left+band} ${y+20}L${left+band} ${y+88}Q${left+band*.45} ${y+48} ${left} ${y+88}Z`}
        stroke={palette[i]} strokeWidth="4" fill={palette[i]} fillOpacity={.08*beat.visible}
        pathLength="1" strokeDasharray="1" strokeDashoffset={1-beat.draw}/>
      <path d={`M${left+band+20} ${y+50}H${labelX-25}`} stroke={palette[i]} strokeWidth="2"/>
      <Icon kind={node.icon} x={left+band/2} y={y+53} size={64} color={palette[i]} reveal={beat.draw}/>
      <Label text={node.label} x={labelX} y={y+55} anchor="start" size={portrait?56:44} maxChars={portrait?15:19}/>
    </g>;
  })}</>;
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
    {photo?<>
      <Img src={image} style={{position:'absolute',inset:0,width:'100%',height:'100%',objectFit:'cover',transform:`scale(${1+.035*Math.min(1,f/Math.max(1,frames*.7))})`}}/>
      <AbsoluteFill style={{background:'linear-gradient(rgba(8,20,29,.65),transparent 34%,rgba(8,20,29,.82))'}}/>
      <div style={{position:'absolute',top:'10%',left:'8%',width:'84%',fontSize:portrait?72:64,fontWeight:700,lineHeight:1.08,textAlign:centered?'center':'left'}}>{spec.title}</div>
      <div style={{position:'absolute',left:'8%',bottom:'25%',width:'84%',display:'flex',gap:30,flexWrap:'wrap'}}>
        {spec.nodes.map((node,i)=>{const beat=beatState(f,i,cues,frames,spec.nodes.length,spec.treatment || 'assemble');
          return <div key={i} style={{fontSize:portrait?40:36,fontWeight:700,opacity:beat.opacity,transform:`translateY(${beat.shift}px) rotate(${beat.rotation}deg)`,borderBottom:`3px solid ${palette[i]}`,paddingBottom:10,textShadow:'0 2px 5px #000'}}>{node.label}</div>;
        })}
      </div>
    </>:<svg viewBox={`0 0 ${w} ${h}`} style={{position:'absolute',left:'4%',width:'92%',top:portrait?'22%':'24%',height:overlay?'56%':portrait?'49%':'52%',overflow:'visible'}}>
      {['flow','transport'].includes(spec.template)&&<Flow {...common}/>}
      {spec.template==='bars'&&<Bars {...common}/>}
      {spec.template==='comparison'&&<Comparison {...common}/>}
      {spec.template==='orbit'&&<Orbit {...common}/>}
      {spec.template==='refraction'&&<Refraction {...common}/>}
      {spec.template==='cycle'&&<Cycle {...common}/>}
      {spec.template==='layers'&&<Layers {...common}/>}
    </svg>}

  </AbsoluteFill>;
}
