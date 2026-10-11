<script lang="ts">
 import {onMount, tick} from 'svelte';
 import {Menu,SquarePen,Plus,ArrowUp,Trash2,X,Settings,PlugZap,BookOpen,ChevronDown,LogOut,Image as ImageIcon,LoaderCircle,Search,Mic,AudioLines,PenLine,Globe,MessageSquare,Camera,Check,RefreshCw,ChevronLeft,ChevronRight,UserRound,Wrench,Boxes,Brain,HardDrive,Save,ShieldCheck,Info,Database, Cpu, Pencil} from 'lucide-svelte';
 import {api,json} from '$lib/api';
 type SettingsTab='overview'|'models'|'skills'|'mcp'|'personalization'|'tools'|'plugins'|'memory';
 type ModelOption={id:string;name:string;model_id:string;is_default:boolean;source:string};
 type Provider={id:string;name:string;model_id:string;base_url:string;enabled:boolean;is_default:boolean;has_api_key:boolean;created:number;updated:number};
 type Chat={id:string;title:string};type Msg={id?:string;role:string;content:string;attachments?:{id:string;filename:string;mime:string}[]};
 let showModelMenu=false, showAttachMenu=false, searching=false, searchText='', dismissedSuggestions:number[]=[], dictating=false, recognizer:any=null, authed=false,checked=false,password='',loginError='',chats:Chat[]=[],active='',messages:Msg[]=[],input='',modelOptions:ModelOption[]=[],model='',online:boolean|null=null,sidebar=false,mode:'chat'|'skills'|'mcp'|'settings'='chat',busy=false,error='',pending:{id:string;filename:string;mime:string}[]=[],fileInput:HTMLInputElement,cameraInput:HTMLInputElement,scrollArea:HTMLElement,skills:any[]=[],servers:any[]=[],skillName='',skillBody='',mcpName='',mcpUrl='',mcpToken='',toolsByServer:Record<string,any[]>={},settingsTab:SettingsTab='overview',profileName='OpenUI',customInstructions='',responseStyle='normal',savingPrefs=false,prefsSaved=false,memories:{id:string;content:string;created:number}[]=[],memoryEnabled=false,newMemory='',storageInfo:{chats:number;messages:number;photos:number;photo_bytes:number;db_bytes:number;memories:number}|null=null;
 let providers:Provider[]=[], editingProvider='',providerName='',providerUrl='',providerModelId='',providerKey='',providerEnabled=true,providerDefault=false,providerClearKey=false,savingProvider=false,testingProvider='',testResults:Record<string,{ok:boolean;http_status:number|null;model_found?:boolean;model_count?:number;note:string}>={};
 onMount(async()=>{try{model=window.localStorage.getItem('openui_selected_model')||'';authed=(await api('/me')).authenticated;if(authed)await init()}catch(e){error=String(e)}finally{checked=true}});
 async function init(){await Promise.all([loadChats(),loadModels()]);try{await loadPreferences()}catch{}}
 async function login(){loginError='';try{await api('/login',json({password}));authed=true;password='';await init()}catch(e){loginError=String(e)}}
 async function logout(){await api('/logout',{method:'POST'});authed=false;messages=[];active=''}
 async function loadChats(){chats=await api('/chats')}
 async function loadModels(){
  try{
   const data=await api('/models');modelOptions=data.options||[];
   if(!modelOptions.some(o=>o.id===model)){model=data.default||modelOptions[0]?.id||'';online=null}
   if(model)window.localStorage.setItem('openui_selected_model',model);
  }catch(e){online=null;error=String(e)}
 }
 function chooseModel(id:string){model=id;online=testResults[id]?.ok??null;showModelMenu=false;window.localStorage.setItem('openui_selected_model',id)}
 function modelName(id:string){return modelOptions.find(o=>o.id===id)?.name||'Chọn mô hình'}
 async function loadProviders(){const r=await api('/providers');providers=r.items}
 function clearProviderForm(){editingProvider='';providerName='';providerUrl='';providerModelId='';providerKey='';providerEnabled=true;providerDefault=false;providerClearKey=false}
 function editProvider(p:Provider){editingProvider=p.id;providerName=p.name;providerUrl=p.base_url;providerModelId=p.model_id;providerKey='';providerEnabled=p.enabled;providerDefault=p.is_default;providerClearKey=false;setTimeout(()=>document.getElementById('provider-name')?.scrollIntoView({behavior:'smooth',block:'center'}),50)}
 async function saveProvider(){
  if(savingProvider)return;savingProvider=true;error='';
  const body={name:providerName.trim(),base_url:providerUrl.trim(),model_id:providerModelId.trim(),api_key:providerKey,enabled:providerEnabled,is_default:providerDefault,clear_api_key:providerClearKey};
  try{
   await api(editingProvider?'/providers/'+editingProvider:'/providers',{method:editingProvider?'PUT':'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   clearProviderForm();await Promise.all([loadProviders(),loadModels()]);
  }catch(e){error=String(e)}finally{savingProvider=false}
 }
 async function deleteProvider(id:string){if(!confirm('Xóa cấu hình mô hình này? Lịch sử chat không bị xóa.'))return;try{await api('/providers/'+id,{method:'DELETE'});if(editingProvider===id)clearProviderForm();await Promise.all([loadProviders(),loadModels()])}catch(e){error=String(e)}}
 async function testProvider(id:string){testingProvider=id;error='';try{const r=await api('/providers/'+id+'/test',{method:'POST'});testResults={...testResults,[id]:r};if(model===id)online=r.ok}catch(e){error=String(e);if(model===id)online=false}finally{testingProvider=''}}

 async function newChat(){active='';messages=[];pending=[];input='';mode='chat';sidebar=false;showAttachMenu=false;dismissedSuggestions=[]}
 async function openChat(id:string){const data=await api('/chats/'+id);active=id;messages=data.messages;mode='chat';sidebar=false;showModelMenu=false;setTimeout(scrollBottom,30)}
 async function deleteChat(id:string){if(!confirm('Xóa cuộc trò chuyện này?'))return;await api('/chats/'+id,{method:'DELETE'});if(active===id)await newChat();await loadChats()}
 function scrollBottom(){if(scrollArea)scrollArea.scrollTop=scrollArea.scrollHeight}
 async function selectFromSidebar(){await setMode('chat');await tick();fileInput?.click()}
 function choosePrompt(text:string){input=text;setTimeout(()=>document.getElementById('chat-input')?.focus(),0)}
 function toggleDictation(){
  if(dictating){recognizer?.stop();dictating=false;return}
  const Speech=(window as any).SpeechRecognition||(window as any).webkitSpeechRecognition;
  if(!Speech){error='Trình duyệt hiện tại không hỗ trợ nhập giọng nói. Hãy thử Safari hoặc Chrome phiên bản mới.';return}
  recognizer=new Speech();recognizer.lang='vi-VN';recognizer.interimResults=false;recognizer.continuous=false;
  recognizer.onresult=(event:any)=>{const text=Array.from(event.results).map((r:any)=>r[0]?.transcript||'').join(' ');input=(input.trim()?input.trim()+' ':'')+text};
  recognizer.onerror=(event:any)=>{error='Không thể thu âm: '+String(event.error||'unknown');dictating=false};
  recognizer.onend=()=>{dictating=false};
  try{recognizer.start();dictating=true}catch(e){error=String(e)}
 }
 async function uploadFiles(e:Event){const target=e.target as HTMLInputElement;const files=Array.from(target.files||[]);if(!files.length)return;error='';try{if(!active){const c=await api('/chats',json({}));active=c.id;await loadChats()}for(const file of files){if(pending.length>=4)throw Error('Tối đa 4 ảnh');if(!['image/jpeg','image/png','image/webp','image/gif'].includes(file.type))throw Error('Chỉ hỗ trợ JPG, PNG, WebP, GIF');if(file.size>8*1024*1024)throw Error('Ảnh tối đa 8 MB');const fd=new FormData();fd.append('file',file);const a=await api('/chats/'+active+'/attachments',{method:'POST',body:fd});pending=[...pending,a]}}catch(e){error=String(e)}finally{target.value=''}}
 async function removeAttachment(id:string){await api('/attachments/'+id,{method:'DELETE'});pending=pending.filter(x=>x.id!==id)}
 async function send(){if(busy||(!input.trim()&&!pending.length))return;busy=true;error='';const text=input.trim(),ids=pending.map(x=>x.id);input='';const attached=[...pending];pending=[];try{if(!active){const c=await api('/chats',json({}));active=c.id}messages=[...messages,{role:'user',content:text,attachments:attached},{role:'assistant',content:''}];setTimeout(scrollBottom,30);const r=await fetch('/api/chats/'+active+'/stream',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:text,attachment_ids:ids,model})});if(!r.ok)throw Error('API HTTP '+r.status);if(!r.body)throw Error('Không có luồng dữ liệu');const reader=r.body.getReader(),decoder=new TextDecoder();let buffer='';while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let boundary;while((boundary=buffer.indexOf('\n\n'))>=0){const packet=buffer.slice(0,boundary);buffer=buffer.slice(boundary+2);for(const line of packet.split('\n')){if(!line.startsWith('data: '))continue;try{const item=JSON.parse(line.slice(6));if(item.delta){messages[messages.length-1].content+=item.delta;messages=[...messages];scrollBottom()}if(item.error)error=item.error}catch{}}}}await loadChats()}catch(e){error=String(e)}finally{busy=false}}
 async function setMode(m:'chat'|'skills'|'mcp'|'settings'){
  mode=m==='chat'?'chat':'settings';sidebar=false;showAttachMenu=false;error='';
  if(m==='chat')return;
  await openSettingsTab(m==='skills'?'skills':m==='mcp'?'mcp':'overview');
 }
 async function openSettingsTab(tab:SettingsTab){
  mode='settings';settingsTab=tab;sidebar=false;error='';prefsSaved=false;
  try{
   if(tab==='models'){await Promise.all([loadProviders(),loadModels()]);}
   if(tab==='skills')skills=await api('/extensions/skills');
   if(tab==='mcp'||tab==='tools')servers=await api('/extensions/mcp');
   if(tab==='personalization')await loadPreferences();
   if(tab==='memory'){await loadMemories();await loadStorage()}
  }catch(e){error=String(e)}
 }
 async function loadPreferences(){const p=await api('/preferences');profileName=p.display_name;customInstructions=p.custom_instructions;responseStyle=p.response_style}
 async function savePreferences(){savingPrefs=true;error='';prefsSaved=false;try{
  await api('/preferences',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({display_name:profileName,custom_instructions:customInstructions,response_style:responseStyle})});prefsSaved=true;
 }catch(e){error=String(e)}finally{savingPrefs=false}}
 async function loadMemories(){const d=await api('/memory');memories=d.items;memoryEnabled=d.enabled}
 async function loadStorage(){storageInfo=await api('/storage')}
 async function toggleMemory(){try{const enabled=!memoryEnabled;await api('/memory/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled})});memoryEnabled=enabled}catch(e){error=String(e)}}
 async function saveMemory(){if(!newMemory.trim())return;try{await api('/memory',json({content:newMemory.trim()}));newMemory='';await loadMemories();await loadStorage()}catch(e){error=String(e)}}
 async function deleteMemory(id:string){try{await api('/memory/'+id,{method:'DELETE'});await loadMemories();await loadStorage()}catch(e){error=String(e)}}
 function formatSize(bytes:number){return bytes<1048576?(bytes/1024).toFixed(1)+' KB':(bytes/1048576).toFixed(1)+' MB'}
 async function saveSkill(){try{await api('/extensions/skills',json({name:skillName,body:skillBody,enabled:true}));skillName='';skillBody='';skills=await api('/extensions/skills')}catch(e){error=String(e)}}
 async function removeSkill(id:string){await api('/extensions/skills/'+id,{method:'DELETE'});skills=await api('/extensions/skills')}
 async function saveMcp(){try{await api('/extensions/mcp',json({name:mcpName,url:mcpUrl,auth:mcpToken,transport:'streamable_http',enabled:true}));mcpName='';mcpUrl='';mcpToken='';servers=await api('/extensions/mcp')}catch(e){error=String(e)}}
 async function removeMcp(id:string){await api('/extensions/mcp/'+id,{method:'DELETE'});servers=await api('/extensions/mcp')}
 async function discover(id:string){try{const r=await api('/extensions/mcp/'+id+'/tools');toolsByServer={...toolsByServer,[id]:r.tools||r}}catch(e){error=String(e)}}
</script>
<svelte:head>
 <title>OpenUI — AI Chat</title>
 <meta name="description" content="OpenUI - AI chat riêng tư"/>
 <meta name="theme-color" content="#000000"/>
 <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover"/>
</svelte:head>
{#if !checked}
 <div class="center"><LoaderCircle size={25} class="spin"/></div>
{:else if !authed}
 <main class="login"><form onsubmit={(e)=>{e.preventDefault();login()}}>
  <div class="brand-symbol">OI</div><h1>Chào mừng đến với OpenUI</h1><p>Đăng nhập để tiếp tục</p>
  <input type="password" placeholder="Mật khẩu" bind:value={password} required autocomplete="current-password"/>
  <button type="submit" class="primary">Tiếp tục</button>{#if loginError}<p class="err">{loginError}</p>{/if}
 </form></main>
{:else}
 <div class="app">
  <aside class:visible={sidebar} aria-label="Thanh bên">
   <div class="aside-head">
    <span class="brand-mark">OI</span>
    <div class="aside-actions">
     <button class="plain-icon" aria-label="Tìm hội thoại" title="Tìm hội thoại" onclick={()=>searching=!searching}><Search size={20}/></button>
     <button class="plain-icon" aria-label="Đóng sidebar" onclick={()=>sidebar=false}><X size={21}/></button>
    </div>
   </div>
   {#if searching}<div class="sidebar-search"><Search size={16}/><input placeholder="Tìm trong lịch sử" bind:value={searchText}/></div>{/if}
   <nav class="main-nav" aria-label="Điều hướng">
    <button class="nav-item new-nav" onclick={newChat}><SquarePen size={20}/> <span>Đoạn chat mới</span></button>
    <button class="nav-item" onclick={selectFromSidebar}><ImageIcon size={20}/> <span>Ảnh</span></button>
    <button class="nav-item" onclick={()=>{setMode('chat');sidebar=false}}><MessageSquare size={20}/> <span>Trò chuyện</span></button>
    <button class="nav-item" onclick={()=>setMode('settings')}><Settings size={20}/> <span>Cài đặt</span></button>
   </nav>
   <div class="history-head">ĐOẠN CHAT GẦN ĐÂY</div>
   <div class="history">
    {#each chats.filter(c=>c.title.toLowerCase().includes(searchText.toLowerCase())) as c(c.id)}
     <div class="history-item" class:chosen={active===c.id&&mode==='chat'}>
      <button class="history-title" onclick={()=>openChat(c.id)} title={c.title}>{c.title}</button>
      <button class="history-del" aria-label="Xóa hội thoại" onclick={()=>deleteChat(c.id)}><Trash2 size={15}/></button>
     </div>
    {/each}
   </div>
   <div class="profile-area"><div class="avatar">OI</div><div class="profile-label"><strong>{profileName}</strong><small>Website AI riêng</small></div><button aria-label="Đăng xuất" class="plain-icon" title="Đăng xuất" onclick={logout}><LogOut size={19}/></button></div>
  </aside>
  {#if sidebar}<button class="scrim" aria-label="Đóng menu" onclick={()=>sidebar=false}></button>{/if}
  <section class="main">
   <header class="topbar">
    <button class="plain-icon menu-button" aria-label="Mở menu" onclick={()=>sidebar=!sidebar}><Menu size={24}/></button>
    <div class="model-switcher">
     <button class="brand-button" aria-label="Chọn mô hình" aria-expanded={showModelMenu} onclick={()=>{showModelMenu=!showModelMenu;showAttachMenu=false}}>
      <span class="current-model-name">{modelName(model)}</span> <ChevronDown size={18} strokeWidth={2}/>
     </button>
     {#if showModelMenu}
      <div class="model-popover" role="menu">
       <div class="popover-title">Chọn mô hình</div>
       {#each modelOptions as m(m.id)}<button class="model-option" onclick={()=>chooseModel(m.id)}><span>{m.name}<small class="model-id-hint">{m.model_id}</small></span>{#if model===m.id}<Check size={17}/>{/if}</button>{/each}{#if !modelOptions.length}<p class="muted" style="padding:8px 12px">Chưa có mô hình nào được bật.</p>{/if}
       <div class="model-status"><span class:online={online===true} class="status-dot"></span> {online===true?'API phản hồi':online===false?'API không kết nối':'Chưa kiểm tra API'}</div>
       <button class="refresh-models" onclick={async()=>{showModelMenu=false;await openSettingsTab('models')}}><Settings size={15}/> Quản lý mô hình và API</button>
      </div>
     {/if}
    </div>
    <div class="top-actions">
     {#if online===false}<span class="offline-dot" title="API kiểm tra không thành công"></span>{/if}
     <button class="plain-icon new-chat-icon" aria-label="Tạo đoạn chat mới" title="Chat mới" onclick={newChat}><SquarePen size={22}/></button>
    </div>
   </header>

   {#if mode==='chat'}
    <div class="chat" bind:this={scrollArea}>
     {#if !messages.length}
      <div class="empty-spacer"></div>
      {#if !input.trim()}
       <div class="suggestions" aria-label="Gợi ý câu hỏi">
        {#if !dismissedSuggestions.includes(0)}<div class="suggestion"><button onclick={selectFromSidebar} class="suggestion-action"><ImageIcon size={19}/> <span>Phân tích ảnh hoặc hình minh họa</span></button><button class="dismiss" aria-label="Ẩn gợi ý" onclick={()=>dismissedSuggestions=[...dismissedSuggestions,0]}><X size={17}/></button></div>{/if}
        {#if !dismissedSuggestions.includes(1)}<div class="suggestion"><button onclick={()=>choosePrompt('Giúp tôi viết hoặc chỉnh sửa nội dung sau: ')} class="suggestion-action"><PenLine size={19}/> <span>Viết hoặc chỉnh sửa</span></button><button class="dismiss" aria-label="Ẩn gợi ý" onclick={()=>dismissedSuggestions=[...dismissedSuggestions,1]}><X size={17}/></button></div>{/if}
        {#if !dismissedSuggestions.includes(2)}<div class="suggestion"><button onclick={()=>choosePrompt('Giải thích chi tiết cho tôi về ')} class="suggestion-action"><Globe size={19}/> <span>Giải thích một chủ đề</span></button><button class="dismiss" aria-label="Ẩn gợi ý" onclick={()=>dismissedSuggestions=[...dismissedSuggestions,2]}><X size={17}/></button></div>{/if}
       </div>
      {/if}
     {:else}
      <div class="thread">
       {#each messages as msg,i}
        <article class:mine={msg.role==='user'} class="message">
         {#if msg.attachments?.length}<div class="images">{#each msg.attachments as a}<img src={'/api/attachments/'+a.id} alt={a.filename}/>{/each}</div>{/if}
         <div class="msgtext">{msg.content}{#if busy&&i===messages.length-1}<span class="cursor">▍</span>{/if}</div>
        </article>
       {/each}
      </div>
     {/if}
    </div>
    <div class="compose-area">
     {#if error}<div class="err toast">{error}<button aria-label="Đóng thông báo" onclick={()=>error=''}><X size={17}/></button></div>{/if}
     <div class="composer">
      {#if pending.length}<div class="images pending">{#each pending as a}<div class="thumb"><img src={'/api/attachments/'+a.id} alt={a.filename}/><button aria-label="Bỏ ảnh" onclick={()=>removeAttachment(a.id)}><X size={14}/></button></div>{/each}</div>{/if}
      <textarea id="chat-input" rows="1" bind:value={input} placeholder="Cứ hỏi nhé" onkeydown={(e)=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}}></textarea>
      <div class="compose-bottom">
       <div class="tools">
        <div class="attachment-wrapper">
         <button class="circle-tool" aria-label="Đính kèm ảnh" aria-expanded={showAttachMenu} onclick={()=>showAttachMenu=!showAttachMenu}><Plus size={24}/></button>
         {#if showAttachMenu}
          <div class="attach-menu">
           <button onclick={()=>{showAttachMenu=false;fileInput?.click()}}><ImageIcon size={18}/> Thêm ảnh từ thư viện</button>
           <button onclick={()=>{showAttachMenu=false;cameraInput?.click()}}><Camera size={18}/> Chụp ảnh</button>
          </div>
         {/if}
         <input bind:this={fileInput} type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple hidden onchange={uploadFiles}/>
         <input bind:this={cameraInput} type="file" accept="image/*" capture="environment" hidden onchange={uploadFiles}/>
        </div>
       </div>
       <div class="right-tools">
        {#if input.trim()||pending.length}
         <button class="send" aria-label="Gửi" disabled={busy} onclick={send}>{#if busy}<LoaderCircle class="spin" size={19}/>{:else}<ArrowUp size={22}/>{/if}</button>
        {:else}
         <button class:recording={dictating} class="mic-button" aria-label="Nhập bằng giọng nói" title="Nhập bằng giọng nói" onclick={toggleDictation}><Mic size={21}/></button>
         <button class="voice-button" aria-label="Nhập bằng giọng nói" title="Nhập bằng giọng nói" onclick={toggleDictation}><AudioLines size={21}/></button>
        {/if}
       </div>
      </div>
     </div>
    </div>
   {:else if mode==='settings'}
    <div class="panel settings-panel">
     {#if settingsTab==='overview'}
      <div class="panel-header settings-title"><Settings size={24}/><h1>Cài đặt</h1></div>
      <p class="settings-intro">Quản lý trải nghiệm OpenUI, công cụ và dữ liệu của bạn.</p>
      <div class="settings-list" aria-label="Danh mục cài đặt">
       <button class="settings-nav" onclick={()=>openSettingsTab('models')}><span class="settings-icon"><Cpu size={21}/></span><span class="settings-meta"><strong>Mô hình</strong><small>Quản lý URL, API key, Model ID, mô hình mặc định</small></span><ChevronRight size={20}/></button>
       <button class="settings-nav" onclick={()=>openSettingsTab('personalization')}><span class="settings-icon"><UserRound size={21}/></span><span class="settings-meta"><strong>Cá nhân hoá</strong><small>Tên, phong cách trả lời và hướng dẫn tùy chỉnh</small></span><ChevronRight size={20}/></button>
       <button class="settings-nav" onclick={()=>openSettingsTab('memory')}><span class="settings-icon"><Brain size={21}/></span><span class="settings-meta"><strong>Bộ nhớ & lưu trữ</strong><small>Ghi nhớ, lịch sử và dung lượng dữ liệu</small></span><ChevronRight size={20}/></button>
       <button class="settings-nav" onclick={()=>openSettingsTab('mcp')}><span class="settings-icon"><PlugZap size={21}/></span><span class="settings-meta"><strong>MCP Servers</strong><small>Thêm và kiểm tra kết nối MCP từ xa</small></span><ChevronRight size={20}/></button>
       <button class="settings-nav" onclick={()=>openSettingsTab('skills')}><span class="settings-icon"><BookOpen size={21}/></span><span class="settings-meta"><strong>Skills</strong><small>Quản lý hướng dẫn SKILL.md</small></span><ChevronRight size={20}/></button>
       <button class="settings-nav" onclick={()=>openSettingsTab('tools')}><span class="settings-icon"><Wrench size={21}/></span><span class="settings-meta"><strong>Tools</strong><small>Xem công cụ từ các MCP server đã kết nối</small></span><ChevronRight size={20}/></button>
       <button class="settings-nav" onclick={()=>openSettingsTab('plugins')}><span class="settings-icon"><Boxes size={21}/></span><span class="settings-meta"><strong>Plugins</strong><small>Trạng thái tích hợp plugin và khả năng mở rộng</small></span><ChevronRight size={20}/></button>
      </div>
      <div class="settings-card compact-card"><div class="status-line"><span class:online={online===true} class="status-dot"></span><span>Model: <strong>{modelName(model)}</strong></span><span class="muted">{online===true?'API phản hồi':online===false?'Không kết nối':'Chưa kiểm tra'}</span></div><button class="subtle-button" onclick={()=>openSettingsTab('models')}><Settings size={16}/> Quản lý</button></div>
     {:else}
      <button class="settings-back" onclick={()=>openSettingsTab('overview')}><ChevronLeft size={20}/> Cài đặt</button>
      {#if settingsTab==='models'}
       <div class="panel-header"><Cpu size={23}/><h1>Mô hình</h1></div>
       <p>Quản lý nhiều API tương thích OpenAI: Colab, Groq, OpenRouter, OpenAI, Ollama qua gateway, hoặc máy chủ riêng. Có thể chọn một model mặc định.</p>
       {#each providers as p(p.id)}
        <div class="entry provider-row">
         <div class="provider-info"><strong>{p.name}</strong><small>{p.model_id}</small><small class="provider-url">{p.base_url}</small><div class="provider-badges">{#if p.is_default}<span>Mặc định</span>{/if}<span class:disabled-tag={!p.enabled}>{p.enabled?'Đang bật':'Đang tắt'}</span><span>{p.has_api_key?'Đã lưu API key':'Không dùng key'}</span></div>
          {#if testResults[p.id]}<small class:probe-ok={testResults[p.id].ok} class:probe-error={!testResults[p.id].ok}>{testResults[p.id].note}{#if testResults[p.id].ok&&testResults[p.id].model_count} · {testResults[p.id].model_count} model trên API{/if}{#if testResults[p.id].ok&&!testResults[p.id].model_found} · Model ID chưa xác nhận{/if}</small>{/if}
         </div>
         <div class="provider-actions">
          <button class="subtle-button" disabled={testingProvider===p.id} onclick={()=>testProvider(p.id)} title="Kiểm tra kết nối API">{#if testingProvider===p.id}<LoaderCircle class="spin" size={15}/>{:else}<RefreshCw size={15}/>{/if} Kiểm tra</button>
          <button class="icon-outline" aria-label={'Sửa '+p.name} title="Sửa cấu hình" onclick={()=>editProvider(p)}><Pencil size={17}/></button>
          <button class="icon-outline" aria-label={'Xóa '+p.name} title="Xóa model" onclick={()=>deleteProvider(p.id)}><Trash2 size={17}/></button>
         </div>
        </div>
       {/each}
       {#if !providers.length}<div class="settings-card"><p>Chưa có mô hình lưu trong database. Cấu hình Colab cũ trong <code>.env</code> vẫn được dùng tạm cho đến khi bạn thêm model đầu tiên.</p></div>{/if}
       <form class="settings-card provider-form" onsubmit={(e)=>{e.preventDefault();saveProvider()}}>
        <h2>{editingProvider?'Chỉnh sửa mô hình':'Thêm mô hình mới'}</h2>
        <label for="provider-name">Tên hiển thị</label><input id="provider-name" placeholder="Ví dụ: Groq — Llama 3.3" maxlength="100" bind:value={providerName} required/>
        <label for="provider-url">API Base URL</label><input id="provider-url" type="url" placeholder="https://api.groq.com/openai/v1" bind:value={providerUrl} required/><small class="muted">Nhập Base URL kết thúc bằng /v1. Cho phép http://127.0.0.1 cho model local.</small>
        <label for="provider-model-id">Model ID chính xác</label><input id="provider-model-id" placeholder="Ví dụ: llama-3.3-70b-versatile" maxlength="180" bind:value={providerModelId} required/>
        <label for="provider-secret">API key {editingProvider?'(để trống nếu giữ key cũ)':'(có thể để trống nếu máy chủ không yêu cầu)'}</label><input id="provider-secret" type="password" autocomplete="new-password" placeholder="••••••••••••••••" bind:value={providerKey}/>
        {#if editingProvider}<label class="check-row"><input type="checkbox" bind:checked={providerClearKey}/> Xóa API key đã lưu</label>{/if}
        <label class="check-row"><input type="checkbox" bind:checked={providerEnabled}/> Bật mô hình này</label>
        <label class="check-row"><input type="checkbox" bind:checked={providerDefault}/> Đặt làm mô hình mặc định</label>
        <div class="provider-actions"><button type="submit" class="primary" disabled={savingProvider||!providerName.trim()||!providerUrl.trim()||!providerModelId.trim()}><Save size={17}/> {savingProvider?'Đang lưu...':editingProvider?'Lưu thay đổi':'Thêm mô hình'}</button>{#if editingProvider}<button type="button" class="subtle-button" onclick={clearProviderForm}>Hủy sửa</button>{/if}</div>
       </form>
      {:else if settingsTab==='skills'}
       <div class="panel-header"><BookOpen size={23}/><h1>Skills</h1></div><p>Quản lý nội dung SKILL.md. Skill được bật sẽ cung cấp hướng dẫn cho model khi trò chuyện.</p>
       <div class="settings-card"><label for="skill-name">Tên skill</label><input id="skill-name" placeholder="Tên skill" bind:value={skillName}/><label for="skill-body">Nội dung SKILL.md</label><textarea id="skill-body" rows="8" placeholder="Nội dung SKILL.md" bind:value={skillBody}></textarea><button class="primary" onclick={saveSkill} disabled={!skillName.trim()||!skillBody.trim()}>Thêm skill</button></div>
       {#each skills as skill}<div class="entry"><div><strong>{skill.name}</strong><small>{skill.enabled?'Đang bật':'Đang tắt'}</small></div><button aria-label="Xóa skill" onclick={()=>removeSkill(skill.id)}><Trash2 size={18}/></button></div>{/each}
       {#if skills.length===0}<p class="empty-notice">Chưa có skill nào.</p>{/if}
      {:else if settingsTab==='mcp'}
       <div class="panel-header"><PlugZap size={23}/><h1>MCP Servers</h1></div><p>Chỉ thêm server HTTPS mà bạn tin tưởng. Không tự động cho phép thực thi công cụ.</p>
       <div class="settings-card"><label for="mcp-name">Tên MCP server</label><input id="mcp-name" placeholder="Tên server" bind:value={mcpName}/><label for="mcp-url">Endpoint HTTPS</label><input id="mcp-url" placeholder="https://mcp.example.com/mcp" bind:value={mcpUrl}/><label for="mcp-token">Bearer token (không bắt buộc)</label><input id="mcp-token" type="password" placeholder="Token" bind:value={mcpToken}/><button class="primary" onclick={saveMcp} disabled={!mcpName.trim()||!mcpUrl.trim()}>Thêm MCP server</button></div>
       {#each servers as server}<div class="entry"><div><strong>{server.name}</strong><small>{server.url}</small>{#if toolsByServer[server.id]}<div class="tool-badges">{#each toolsByServer[server.id] as tool}<span>{tool.name}</span>{/each}</div>{/if}</div><button onclick={()=>discover(server.id)}>Tools</button><button aria-label="Xóa server" onclick={()=>removeMcp(server.id)}><Trash2 size={18}/></button></div>{/each}
       {#if servers.length===0}<p class="empty-notice">Chưa có MCP server nào.</p>{/if}
      {:else if settingsTab==='personalization'}
       <div class="panel-header"><UserRound size={23}/><h1>Cá nhân hoá</h1></div><p>Tùy chỉnh thông tin và cách AI trả lời. Thay đổi được lưu trên VPS.</p>
       <div class="settings-card"><label for="profile-name">Tên hiển thị</label><input id="profile-name" maxlength="80" bind:value={profileName}/><label for="response-style">Phong cách trả lời</label><select id="response-style" bind:value={responseStyle}><option value="normal">Mặc định</option><option value="brief">Ngắn gọn</option><option value="detailed">Chi tiết</option></select><label for="custom-instructions">Hướng dẫn tùy chỉnh cho AI</label><textarea id="custom-instructions" rows="7" maxlength="6000" placeholder="Ví dụ: Luôn trả lời bằng tiếng Việt..." bind:value={customInstructions}></textarea><button class="primary" disabled={savingPrefs||!profileName.trim()} onclick={savePreferences}><Save size={16}/> {savingPrefs?'Đang lưu...':'Lưu thay đổi'}</button>{#if prefsSaved}<p class="success-text"><Check size={16}/> Đã lưu vào database.</p>{/if}</div>
      {:else if settingsTab==='memory'}
       <div class="panel-header"><Brain size={23}/><h1>Bộ nhớ & lưu trữ</h1></div><p>Quản lý những điều bạn chủ động cho phép AI ghi nhớ và dung lượng lịch sử trên VPS.</p>
       <div class="settings-card"><div class="memory-toggle-row"><div><strong>Sử dụng bộ nhớ đã lưu</strong><small>Khi bật, các ghi nhớ bên dưới được đưa vào ngữ cảnh AI.</small></div><button class:enabled={memoryEnabled} class="toggle" role="switch" aria-checked={memoryEnabled} aria-label="Bật hoặc tắt bộ nhớ" onclick={toggleMemory}><span></span></button></div><label for="new-memory">Thêm ghi nhớ</label><textarea id="new-memory" rows="3" maxlength="1200" placeholder="Ví dụ: Ưu tiên hướng dẫn triển khai VPS bằng lệnh copy-paste..." bind:value={newMemory}></textarea><button class="primary" disabled={!newMemory.trim()} onclick={saveMemory}><Plus size={17}/> Lưu ghi nhớ</button></div>
       {#each memories as memory}<div class="entry"><div><span>{memory.content}</span></div><button aria-label="Xóa ghi nhớ" onclick={()=>deleteMemory(memory.id)}><Trash2 size={18}/></button></div>{/each}
       {#if memories.length===0}<p class="empty-notice">Chưa lưu ghi nhớ nào. Bộ nhớ không tự thu thập thông tin từ cuộc trò chuyện.</p>{/if}
       {#if storageInfo}<div class="settings-card"><h2>Thống kê lưu trữ</h2><div class="stat-grid"><div><strong>{storageInfo.chats}</strong><small>Hội thoại</small></div><div><strong>{storageInfo.messages}</strong><small>Tin nhắn</small></div><div><strong>{storageInfo.photos}</strong><small>Ảnh</small></div><div><strong>{formatSize(storageInfo.db_bytes)}</strong><small>SQLite</small></div></div><p>Ảnh chiếm khoảng {formatSize(storageInfo.photo_bytes)} trong database. Dữ liệu nằm trên VPS, không phụ thuộc Colab.</p></div>{/if}
      {:else if settingsTab==='tools'}
       <div class="panel-header"><Wrench size={23}/><h1>Tools</h1></div><p>Danh sách công cụ được cung cấp bởi MCP server. Khám phá công cụ không đồng nghĩa với cho phép AI thực thi.</p>
       {#if servers.length===0}<div class="settings-card empty-notice">Chưa có MCP server. <button class="text-button" onclick={()=>openSettingsTab('mcp')}>Thêm MCP server</button></div>{/if}
       {#each servers as server}<div class="settings-card"><div class="tool-server-line"><strong>{server.name}</strong><button class="subtle-button" onclick={()=>discover(server.id)}><RefreshCw size={15}/> Khám phá tools</button></div><small class="muted">{server.url}</small>{#if toolsByServer[server.id]}{#each toolsByServer[server.id] as tool}<div class="tool-detail"><strong>{tool.name}</strong><small>{tool.description||'Không có mô tả'}</small></div>{/each}{:else}<p class="muted">Chưa tải danh sách tools.</p>{/if}</div>{/each}
      {:else if settingsTab==='plugins'}
       <div class="panel-header"><Boxes size={23}/><h1>Plugins</h1></div><div class="settings-card"><div class="notice-heading"><Info size={19}/><strong>Chưa kích hoạt Plugin Manager</strong></div><p>OpenUI hiện chưa có cơ chế cài đặt và chạy plugin độc lập. Không hiển thị plugin giả hoặc nút cài đặt không hoạt động.</p><p>Trong thời gian này, các tích hợp công cụ qua MCP được quản lý ở mục MCP Servers.</p><button class="subtle-button" onclick={()=>openSettingsTab('mcp')}><PlugZap size={16}/> Mở MCP Servers <ChevronRight size={16}/></button></div>
      {/if}
     {/if}
     {#if error}<div class="toast settings-error" role="alert">{error}<button aria-label="Đóng lỗi" onclick={()=>error=''}><X size={16}/></button></div>{/if}
    </div>
   {/if}
  </section>
 </div>
{/if}
<style>
:global(*){box-sizing:border-box}
:global(html){height:100%;background:#000}
:global(body){margin:0;background:#000;color:#f4f4f4;font:16px -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;-webkit-font-smoothing:antialiased}
:global(button),:global(input),:global(textarea){font:inherit}
:global(button){cursor:pointer;-webkit-tap-highlight-color:transparent}
:global(button:disabled){opacity:.42;cursor:not-allowed}
:global(button:focus-visible),:global(input:focus-visible),:global(textarea:focus-visible){outline:2px solid #6396f5;outline-offset:3px}
:global(::selection){background:#4266ad}
.app{display:flex;height:100dvh;min-height:0;overflow:hidden;background:#000}
.center{height:100dvh;display:grid;place-items:center}
.login{height:100dvh;display:grid;place-items:center;padding:24px}
.login form{width:min(380px,100%);display:flex;flex-direction:column;gap:18px;text-align:center}
.login h1{font-size:25px;margin:2px 0 0;letter-spacing:-.7px}
.login p{margin:0;color:#999}
.brand-symbol{background:#f3f3f3;color:#050505;width:49px;height:49px;display:grid;place-items:center;border-radius:14px;font-weight:800;letter-spacing:-1.5px;margin:0 auto}
.login input,.settings-card input,.settings-card textarea{background:#232323;color:white;border:1px solid #484848;border-radius:13px;padding:14px;width:100%;font-size:16px}
.primary{background:#f3f3f3;color:#111;border:0;border-radius:24px;padding:12px 20px;font-weight:650}
.err{color:#f6b8b8;font-size:14px}.toast{display:flex;align-items:center;justify-content:space-between;gap:10px;background:#332324;border-radius:13px;padding:11px 13px;margin-bottom:9px}.toast button{border:0;background:transparent;color:#fff;padding:2px}
aside{width:275px;background:#0b0b0b;display:flex;flex-direction:column;padding:15px 12px 12px;flex-shrink:0;gap:6px;border-right:1px solid #171717}
.aside-head{display:flex;align-items:center;justify-content:space-between;padding:0 9px 15px;height:48px}
.brand-mark{font-size:18px;font-weight:850;border-radius:50%;width:28px;height:28px;display:grid;place-items:center;background:#eee;color:#090909;letter-spacing:-1.5px}
.aside-actions{display:flex;align-items:center;gap:7px}
.plain-icon{border:0;color:#ededed;background:transparent;border-radius:10px;width:37px;height:37px;display:grid;place-items:center;padding:0}
.plain-icon:hover,.plain-icon:focus-visible{background:#242424}
.sidebar-search{display:flex;align-items:center;gap:8px;background:#202020;border:1px solid #333;border-radius:10px;padding:8px 12px;color:#a5a5a5;margin-bottom:7px}
.sidebar-search input{width:100%;min-width:0;background:transparent;border:0;outline:0;color:#fff;font-size:14px}
.main-nav{display:grid;gap:4px}
.nav-item{background:transparent;border:0;color:#f0f0f0;text-align:left;display:flex;align-items:center;gap:14px;width:100%;min-height:43px;border-radius:11px;padding:9px 12px;white-space:nowrap}
.nav-item:hover{background:#212121}
.new-nav{background:#1b1b1b;margin:7px 0 6px}
.nav-item span{font-size:15px}
.history-head{color:#898989;font-size:11px;font-weight:600;letter-spacing:.35px;padding:26px 10px 9px}
.history{overflow-y:auto;flex:1;min-height:0}
.history-item{display:flex;align-items:center;border-radius:10px;min-height:40px}
.history-item.chosen,.history-item:hover{background:#1c1c1c}
.history-title{background:transparent;border:0;color:#e4e4e4;text-align:left;padding:10px 12px;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px}
.history-del{background:transparent;color:#969696;border:0;padding:7px;opacity:0}.history-item:hover .history-del{opacity:1}
.profile-area{display:flex;align-items:center;gap:10px;padding:12px 5px 4px;border-top:1px solid #202020}
.avatar{background:#3269ce;color:#fff;width:33px;height:33px;border-radius:50%;display:grid;place-items:center;font-weight:550;font-size:13px}
.profile-label{display:flex;flex-direction:column;flex:1;min-width:0}.profile-label strong{font-size:14px;font-weight:570}.profile-label small{color:#888;font-size:12px;margin-top:3px}
.scrim{display:none}
.main{display:flex;flex-direction:column;flex:1;min-width:0;background:#000}
.topbar{height:64px;flex:0 0 64px;display:flex;align-items:center;padding:0 23px;gap:18px;position:relative;z-index:5}
.menu-button{margin-left:-8px}
.brand-button{display:flex;align-items:center;gap:6px;padding:5px 0;background:none;border:0;color:#f2f2f2;font-size:19px;font-weight:650;white-space:nowrap;letter-spacing:-.5px;max-width:min(55vw,345px);min-width:0}.brand-button :global(svg){flex-shrink:0}.current-model-name{min-width:0;overflow:hidden;text-overflow:ellipsis}
.model-switcher{position:relative;min-width:0}
.top-actions{margin-left:auto;display:flex;align-items:center;gap:9px}
.offline-dot,.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#858585;flex-shrink:0}
.status-dot.online{background:#65bc84}
.model-popover{position:absolute;top:calc(100% + 13px);left:0;width:min(300px,calc(100vw - 35px));background:#242424;border:1px solid #3a3a3a;border-radius:15px;box-shadow:0 15px 38px #0009;overflow:hidden;padding:8px;z-index:10}
.popover-title{padding:9px 12px;color:#aaa;font-size:13px}
.model-option,.refresh-models{display:flex;justify-content:space-between;align-items:center;gap:10px;width:100%;border:0;background:none;color:#f0f0f0;border-radius:9px;padding:11px 12px;text-align:left;font-size:14px;overflow-wrap:anywhere}
.model-option:hover,.refresh-models:hover{background:#363636}
.model-id-hint{display:block;color:#999;font-size:11px;margin-top:5px;overflow-wrap:anywhere}
.model-status{padding:10px 12px;color:#aaa;font-size:12px;border-top:1px solid #424242;display:flex;gap:9px;align-items:center}
.refresh-models{justify-content:flex-start;font-size:12px}
.chat{flex:1;min-height:0;overflow-y:auto;display:flex;flex-direction:column;overscroll-behavior:contain;scrollbar-color:#383838 transparent}
.empty-spacer{flex:1;min-height:10px}
.suggestions{margin:0 auto 16px;padding:0 16px;width:min(780px,100%);display:grid;gap:2px}
.suggestion{display:flex;align-items:center;min-height:47px;border-radius:10px}
.suggestion-action{flex:1;min-width:0;background:transparent;border:0;color:#bcbcbc;display:flex;align-items:center;text-align:left;gap:17px;padding:10px 8px;font-size:16px}
.suggestion-action:hover{color:#fff}
.suggestion-action :global(svg){flex-shrink:0;color:#a9a9a9}
.dismiss{border:0;background:none;color:#aaa;padding:10px;border-radius:8px}
.dismiss:hover{background:#252525}
.thread{max-width:815px;width:100%;margin:0 auto;padding:22px 28px 40px;display:flex;flex-direction:column;gap:30px}
.message{max-width:100%;align-self:flex-start;line-height:1.65;min-width:0}
.message.mine{background:#262626;padding:12px 17px;border-radius:20px;max-width:86%;align-self:flex-end}
.msgtext{white-space:pre-wrap;overflow-wrap:anywhere;font-size:15px}
.cursor{opacity:.7;animation:blink 1s step-end infinite}@keyframes blink{50%{opacity:.2}}
.compose-area{width:min(810px,100%);padding:0 15px max(22px,env(safe-area-inset-bottom));margin:0 auto;flex-shrink:0;position:relative;z-index:4}
.composer{background:#222;border:1px solid #2a2a2a;border-radius:26px;padding:12px 14px 10px;box-shadow:0 3px 15px #0003}
.composer textarea{resize:none;outline:none;border:0;background:transparent;color:#f4f4f4;width:100%;min-height:37px;max-height:160px;font-size:16px;line-height:1.45;display:block;padding:6px 2px 9px}
.composer textarea::placeholder{color:#a4a4a4;opacity:1}
.compose-bottom{display:flex;align-items:center;justify-content:space-between;min-height:42px}
.tools,.right-tools{display:flex;align-items:center;gap:10px}
.attachment-wrapper{position:relative}
.circle-tool{background:#343434;border:0;color:white;width:38px;height:38px;border-radius:50%;display:grid;place-items:center}
.circle-tool:hover{background:#454545}
.attach-menu{position:absolute;left:0;bottom:calc(100% + 12px);width:240px;background:#272727;border:1px solid #424242;box-shadow:0 12px 32px #000a;padding:7px;border-radius:14px}
.attach-menu button{display:flex;align-items:center;gap:11px;background:transparent;color:#eee;border:0;padding:12px 10px;width:100%;text-align:left;border-radius:9px;font-size:14px}
.attach-menu button:hover{background:#383838}
.mic-button{display:grid;place-items:center;width:35px;height:35px;color:#e9e9e9;background:#313131;border:0;border-radius:50%}
.mic-button.recording{background:#873e40;color:#fff;animation:pulse 1.5s ease-in-out infinite}@keyframes pulse{50%{box-shadow:0 0 0 7px #873e4044}}
.voice-button{display:grid;place-items:center;width:38px;height:38px;background:#2865c7;color:#fff;border:0;border-radius:50%}
.send{display:grid;place-items:center;background:#eee;color:#131313;border:0;width:38px;height:38px;border-radius:50%}
.images{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0}.images img{width:105px;height:105px;object-fit:cover;border-radius:13px}.thumb{position:relative}.thumb button{position:absolute;right:3px;top:3px;background:#111;color:#fff;border:0;border-radius:50%;width:25px;height:25px;display:grid;place-items:center}
.panel{overflow-y:auto;max-width:840px;width:100%;padding:30px 24px;margin:0 auto;min-height:0}.panel-header{display:flex;align-items:center;gap:13px}.panel h1{font-size:27px;letter-spacing:-.8px;font-weight:600;margin:8px 0}.panel>p,.settings-card p{color:#aaa}.settings-card{background:#191919;border:1px solid #303030;padding:20px;border-radius:17px;display:grid;gap:12px;margin:23px 0}.entry{display:flex;align-items:center;gap:12px;justify-content:space-between;background:#1d1d1d;border-radius:14px;padding:15px;margin:9px 0}.entry>div{flex:1;min-width:0;overflow-wrap:anywhere}.entry small{display:block;color:#aaa;margin-top:7px}.entry button{background:#333;color:white;border:0;border-radius:9px;padding:9px}
:global(.spin){animation:spin 1s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}

.settings-panel{max-width:710px;padding-bottom:45px}
.settings-title{margin-top:11px}.settings-intro{margin:7px 0 26px;font-size:14px}
.settings-list{display:flex;flex-direction:column;gap:3px;background:#151515;border:1px solid #292929;border-radius:17px;padding:7px;margin:20px 0}
.settings-nav{display:flex;align-items:center;gap:14px;border:0;border-radius:12px;width:100%;text-align:left;background:transparent;color:#f1f1f1;padding:13px 12px;min-height:70px}
.settings-nav:hover,.settings-nav:focus-visible{background:#292929}
.settings-icon{width:39px;height:39px;display:grid;place-items:center;border-radius:12px;background:#282828;flex-shrink:0}
.settings-meta{flex:1;min-width:0;display:flex;flex-direction:column;gap:5px}.settings-meta strong{font-size:15px;font-weight:580}.settings-meta small{font-size:12px;line-height:1.4;color:#a4a4a4}
.settings-nav :global(svg){flex-shrink:0}.settings-nav> :global(svg:last-child){color:#858585}
.settings-back{display:flex;align-items:center;gap:4px;background:none;color:#b8b8b8;padding:7px 2px;border:0;margin-bottom:18px;font-size:14px}
.settings-back:hover{color:white}.settings-card label{font-size:13px;font-weight:600;color:#dedede}
.settings-card select{width:100%;padding:13px 14px;background:#232323;color:#f4f4f4;border:1px solid #484848;border-radius:13px;font-size:16px}
.settings-card .primary{display:flex;align-items:center;justify-content:center;gap:9px}
.compact-card{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:14px}
.status-line{display:flex;align-items:center;gap:9px;font-size:13px;min-width:0;flex-wrap:wrap}.status-line strong{font-weight:600}.muted{font-size:12px;color:#929292}
.subtle-button{display:inline-flex;align-items:center;justify-content:center;gap:7px;background:#333;color:#eee;border:1px solid #4a4a4a;border-radius:10px;padding:9px 12px;font-size:13px;min-height:35px}
.subtle-button:hover{background:#454545}.success-text{display:flex;align-items:center;gap:7px;color:#a6ddb7!important;font-size:13px}
.empty-notice{color:#969696;font-size:14px;padding:14px 4px}.settings-error{margin-top:20px}
.memory-toggle-row{display:flex;align-items:center;justify-content:space-between;gap:18px}.memory-toggle-row div{display:flex;flex-direction:column;gap:7px}
.memory-toggle-row small{color:#a5a5a5;line-height:1.4;font-size:12px}.toggle{display:flex;align-items:center;border:0;border-radius:40px;background:#555;width:47px;height:27px;padding:3px;flex-shrink:0;transition:background .15s}
.toggle.enabled{background:#3f7fd9}.toggle span{display:block;width:21px;height:21px;background:white;border-radius:50%;transition:transform .15s}.toggle.enabled span{transform:translateX(20px)}
.stat-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.stat-grid div{display:flex;flex-direction:column;gap:7px}.stat-grid strong{font-size:18px}.stat-grid small{font-size:11px;color:#aaa}
.tool-server-line{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap}.tool-detail{padding:10px 0;border-top:1px solid #333;display:flex;flex-direction:column;gap:5px}.tool-detail small{color:#a9a9a9;font-size:12px;line-height:1.5}
.tool-badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:9px}.tool-badges span{background:#303030;color:#d0d0d0;border-radius:7px;padding:5px 7px;font-size:12px}
.provider-row{display:flex;align-items:flex-start;flex-wrap:wrap;gap:14px}.provider-info{flex:1;min-width:210px}.provider-url{overflow-wrap:anywhere}.provider-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.provider-actions .primary{display:flex;align-items:center;gap:9px}.provider-row .provider-actions button{white-space:nowrap}.provider-badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.provider-badges span{font-size:11px;background:#303030;border-radius:7px;padding:5px 7px;color:#ddd}.provider-badges .disabled-tag{opacity:.5}.icon-outline{display:inline-grid;place-items:center;min-width:35px;min-height:35px;border:1px solid #404040!important;border-radius:10px!important}.provider-form{margin-top:25px}.check-row{display:flex;align-items:center;gap:11px;font-weight:400!important;font-size:14px!important;color:#e1e1e1!important}.settings-card .check-row input{width:18px;height:18px;accent-color:#dedede;padding:0;flex-shrink:0}.probe-ok{color:#98d8a7!important}.probe-error{color:#f3a4a4!important}.provider-form code,.settings-card code{font-size:12px;overflow-wrap:anywhere}
.notice-heading{display:flex;align-items:center;gap:10px}.settings-card h2{font-size:16px;margin:0}.text-button{color:#d8d8d8;text-decoration:underline;background:transparent;border:0;padding:3px}
@media(max-width:760px){.settings-list{margin:16px 0}.settings-nav{min-height:64px}.settings-nav{padding:11px 9px}.settings-card{padding:16px}.stat-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:760px){
 aside{position:fixed;z-index:30;left:0;top:0;bottom:0;width:min(80vw,280px);transform:translateX(-101%);transition:transform .2s ease;border-right:1px solid #161616;padding-top:20px}
 aside.visible{transform:translateX(0)}
 .history-del{opacity:1}
 .scrim{display:block;position:fixed;inset:0;z-index:29;background:#0009;border:0}
 .topbar{height:57px;flex-basis:57px;padding:0 15px;gap:14px}
 .brand-button{font-size:18px}
 .compose-area{padding:0 15px max(18px,env(safe-area-inset-bottom))}
 .composer{border-radius:24px;padding:10px 12px 9px}
 .composer textarea{padding:4px 3px 7px;min-height:37px}
 .suggestions{padding:0 19px;margin-bottom:15px}
 .suggestion{min-height:47px}
 .suggestion-action{font-size:15px;gap:17px}
 .thread{padding:16px 18px 25px;gap:23px}
 .panel{padding:18px}
}
@media(max-width:350px){.brand-button{font-size:16px}.topbar{gap:7px}.compose-area{padding-left:9px;padding-right:9px}}
</style>
