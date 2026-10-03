import React,{useEffect,useMemo,useState}from"react";
import{CalendarDays,CheckCircle2,Clock3,Plus,Sparkles,Star,Trash2,Users,X}from"lucide-react";
const API="http://127.0.0.1:8000";
const DAYS=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
const load=(k,d)=>{try{return JSON.parse(localStorage.getItem(k))??d}catch{return d}};
const save=(k,v)=>localStorage.setItem(k,JSON.stringify(v));
const to24=t=>{const[m,p]=t.split(" ");let[h,min]=m.split(":").map(Number);if(p==="PM"&&h!==12)h+=12;if(p==="AM"&&h===12)h=0;return String(h).padStart(2,"0")+":"+String(min).padStart(2,"0")};
const uid=()=>Date.now()+Math.floor(Math.random()*1000);
function Modal({title,onClose,children}){return <div className="overlay"><div className="modal"><div className="modal-head"><h2>{title}</h2><button onClick={onClose}><X size={18}/></button></div>{children}</div></div>}
export default function App(){
 const[tasks,setTasks]=useState(()=>load("dayflow_tasks",[]));
 const[blocks,setBlocks]=useState(()=>load("dayflow_blocks",[]));
 const[plan,setPlan]=useState(()=>load("dayflow_plan",[]));
 const[profile,setProfile]=useState(()=>load("dayflow_profile",{name:"You",start:"08:00",end:"21:00"}));
 const[meetings,setMeetings]=useState(()=>load("dayflow_meetings",[]));
 const[status,setStatus]=useState("Connecting…"),[modal,setModal]=useState(null),[options,setOptions]=useState([]);
 const[chat,setChat]=useState([{who:"ai",text:"Hey 👋 Add your fixed commitments and tasks, then I’ll build around them."}]);
 const[input,setInput]=useState("");
 useEffect(()=>{fetch(API+"/api/health").then(r=>r.json()).then(()=>setStatus("Planner online")).catch(()=>setStatus("Backend offline"))},[]);
 useEffect(()=>save("dayflow_tasks",tasks),[tasks]);useEffect(()=>save("dayflow_blocks",blocks),[blocks]);useEffect(()=>save("dayflow_plan",plan),[plan]);useEffect(()=>save("dayflow_profile",profile),[profile]);useEffect(()=>save("dayflow_meetings",meetings),[meetings]);
 const availability=useMemo(()=>DAYS.map((_,day)=>({day,start:profile.start,end:profile.end})),[profile]);
 const open=tasks.filter(t=>!t.completed), minutes=open.reduce((a,t)=>a+Number(t.duration),0);
 async function planWeek(){try{const r=await fetch(API+"/api/plan",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({tasks:open,fixed_blocks:blocks,availability})});const d=await r.json();if(!r.ok)throw Error(JSON.stringify(d));setPlan(d.schedule);setChat(c=>[...c,{who:"ai",text:d.message}])}catch(e){alert("Start the FastAPI backend first. "+e.message)}}
 function submitTask(e){e.preventDefault();const f=new FormData(e.currentTarget);setTasks(v=>[...v,{id:uid(),title:f.get("title"),category:f.get("category"),date:f.get("date")||null,duration:Number(f.get("duration")),priority:f.get("priority"),completed:false,starred:false}]);setModal(null)}
 function submitBlock(e){e.preventDefault();const f=new FormData(e.currentTarget);setBlocks(v=>[...v,{id:uid(),title:f.get("title"),type:f.get("type"),day:Number(f.get("day")),start:f.get("start"),end:f.get("end")}]);setModal(null)}
 async function propose(e){e.preventDefault();const f=new FormData(e.currentTarget);const payload={title:f.get("title"),duration:Number(f.get("duration")),urgency:f.get("urgency"),participants:[{name:f.get("person"),availability}],fixed_blocks:blocks,availability,preferred_after:f.get("after")||null};const r=await fetch(API+"/api/meetings/propose",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const d=await r.json();setOptions(d.options||[]);setModal({type:"options",title:payload.title})}
 function confirmMeeting(o,title){const b={id:uid(),title,type:"Meeting",day:o.day,start:to24(o.start),end:to24(o.end)};setBlocks(v=>[...v,b]);setMeetings(v=>[...v,{...b,date:o.date}]);setOptions([]);setModal(null)}
 function send(){if(!input.trim())return;setChat(c=>[...c,{who:"me",text:input},{who:"ai",text:"Got it. For now I’ll use your calendar, tasks, availability, and meeting tools to make the schedule. Gemini plugs into this assistant next."}]);setInput("")}
 return <div className="shell">
  <aside className="sidebar"><div className="brand"><div className="logo">✦</div><div><h1>DayFlow</h1><p>Your day, figured out.</p></div></div><div className="status"><i/> {status}</div>
   <div className="intro"><small>AI PLANNER</small><h2>A little structure.<br/>A lot more breathing room.</h2><p>Classes, work, assignments, meetings — messy is fine.</p></div>
   <div className="chat">{chat.map((m,i)=><div key={i} className={"bubble "+m.who}>{m.text}</div>)}</div>
   <div className="quick"><button onClick={()=>setModal("block")}><Plus size={15}/> Fixed block</button><button onClick={()=>setModal("meeting")}><Users size={15}/> Meeting</button></div>
   <div className="composer"><textarea value={input} onChange={e=>setInput(e.target.value)} placeholder="Tell DayFlow what’s going on…"/><button onClick={send}>➤</button></div>
  </aside>
  <main><header><div><small>YOUR WEEK</small><h2>Good to see you, {profile.name} 👋</h2><p>Build around the things that can’t move.</p></div><div className="actions"><button className="ghost" onClick={()=>setModal("profile")}>Profile</button><button className="primary" onClick={planWeek}><Sparkles size={16}/> Plan my week</button></div></header>
   <section className="stats"><Stat icon={<CheckCircle2/>} label="Open tasks" value={open.length}/><Stat icon={<Clock3/>} label="To schedule" value={(minutes/60).toFixed(1)+"h"}/><Stat icon={<CalendarDays/>} label="Fixed blocks" value={blocks.length}/><Stat icon={<Users/>} label="Meetings" value={meetings.length}/></section>
   <section className="card calendar"><div className="card-title"><div><h3>Weekly routine</h3><p>AI focus blocks automatically avoid fixed commitments.</p></div><button onClick={()=>setModal("block")}><Plus size={15}/> Add block</button></div>
    <div className="week">{DAYS.map((d,day)=><div className="day" key={d}><b>{d}</b><div className="daybody">{blocks.filter(x=>x.day===day).map(x=><Block key={"b"+x.id} x={x} fixed onDelete={()=>setBlocks(v=>v.filter(q=>q.id!==x.id))}/>)}{plan.filter(x=>x.day===day).map((x,i)=><Block key={"p"+i} x={{...x,start:to24(x.start),end:to24(x.end),type:"AI"}}/>)}</div></div>)}</div>
   </section>
   <section className="bottom"><div className="card"><div className="card-title"><div><small>YOUR WORKLOAD</small><h3>Tasks</h3></div><button onClick={()=>setModal("task")}><Plus size={15}/> Add task</button></div>
    <div className="tasklist">{tasks.length?tasks.map(t=><div className={"task "+(t.completed?"done":"")} key={t.id}><button className="check" onClick={()=>setTasks(v=>v.map(x=>x.id===t.id?{...x,completed:!x.completed}:x))}>{t.completed?"✓":""}</button><div><b>{t.title}</b><span>{t.category} · {t.duration} min {t.date?"· due "+t.date:""}</span></div><button className={"star "+(t.starred?"on":"")} onClick={()=>setTasks(v=>v.map(x=>x.id===t.id?{...x,starred:!x.starred}:x))}><Star size={15}/></button><em className={"p "+t.priority}>{t.priority}</em><button className="trash" onClick={()=>setTasks(v=>v.filter(x=>x.id!==t.id))}><Trash2 size={15}/></button></div>):<div className="empty">No tasks yet. Add one and DayFlow will find the time.</div>}</div>
   </div><div className="card insight"><Sparkles/><small>DAYFLOW INSIGHT</small><h3>Your constraints are the plan.</h3><p>DayFlow schedules flexible work around classes, work, meetings, and your availability instead of pretending every hour is free.</p><button className="primary wide" onClick={planWeek}>Build my plan</button></div></section>
  </main>
  {modal==="task"&&<Modal title="Add task" onClose={()=>setModal(null)}><form onSubmit={submitTask}><Field n="title" l="Task" required/><div className="row"><Select n="category" l="Category" opts={["School","Work","Personal","Club"]}/><Field n="duration" l="Minutes" type="number" min="15" defaultValue="60"/></div><div className="row"><Field n="date" l="Deadline" type="date"/><Select n="priority" l="Priority" opts={["high","medium","low"]}/></div><Submit/></form></Modal>}
  {modal==="block"&&<Modal title="Add fixed block" onClose={()=>setModal(null)}><form onSubmit={submitBlock}><Field n="title" l="Commitment" required/><div className="row"><Select n="type" l="Type" opts={["Class","Work","Study","Personal","Meeting"]}/><Select n="day" l="Day" opts={DAYS} values={[0,1,2,3,4,5,6]}/></div><div className="row"><Field n="start" l="Start" type="time" defaultValue="09:00"/><Field n="end" l="End" type="time" defaultValue="10:00"/></div><Submit/></form></Modal>}
  {modal==="profile"&&<Modal title="Your availability" onClose={()=>setModal(null)}><form onSubmit={e=>{e.preventDefault();const f=new FormData(e.currentTarget);setProfile({name:f.get("name"),start:f.get("start"),end:f.get("end")});setModal(null)}}><Field n="name" l="Name" defaultValue={profile.name}/><div className="row"><Field n="start" l="Available from" type="time" defaultValue={profile.start}/><Field n="end" l="Available until" type="time" defaultValue={profile.end}/></div><Submit/></form></Modal>}
  {modal==="meeting"&&<Modal title="Find a meeting time" onClose={()=>setModal(null)}><form onSubmit={propose}><Field n="title" l="Meeting" required/><Field n="person" l="Participant" placeholder="David"/><div className="row"><Field n="duration" l="Minutes" type="number" defaultValue="60"/><Select n="urgency" l="Urgency" opts={["normal","urgent"]}/></div><Field n="after" l="Prefer after" type="time"/><Submit text="Find 3 times"/></form></Modal>}
  {modal?.type==="options"&&<Modal title="Pick a meeting time" onClose={()=>setModal(null)}><div className="options">{options.length?options.map(o=><button key={o.id} onClick={()=>confirmMeeting(o,modal.title)}><b>{DAYS[o.day]} · {o.date}</b><span>{o.start} – {o.end}</span><small>{o.reason}</small></button>):<p>No mutual time found. Try broader availability.</p>}</div></Modal>}
 </div>
}
function Stat({icon,label,value}){return <div className="stat"><span>{icon}</span><div><small>{label}</small><b>{value}</b></div></div>}
function Block({x,fixed,onDelete}){return <div className={"block "+String(x.type).toLowerCase()}><b>{x.title}</b><span>{x.start}–{x.end}</span>{fixed&&<button onClick={onDelete}>×</button>}</div>}
function Field({n,l,...p}){return <label>{l}<input name={n} {...p}/></label>}
function Select({n,l,opts,values}){return <label>{l}<select name={n}>{opts.map((o,i)=><option key={o} value={values?values[i]:o}>{o}</option>)}</select></label>}
function Submit({text="Save"}){return <button className="primary submit" type="submit">{text}</button>}
