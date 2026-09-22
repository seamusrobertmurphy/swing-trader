import re,subprocess,sys,pathlib
sys.path.insert(0,"03-inputs"); import control_eval as ce; from control_centre import app
S=pathlib.Path(sys.argv[1])
PROBE="""<script>window.addEventListener('load',function(){var out=[];
document.querySelectorAll('.briefrow').forEach(function(row,i){var left=row.children[0],right=row.children[1];
var h3=row.querySelector('h3');var name=h3?h3.textContent.trim().slice(0,28):'?';
var lt=left?left.getBoundingClientRect().height:0; var tools=0,charts=0,n=0;
if(right){Array.from(right.querySelectorAll(':scope > *, :scope > .tools > *')).forEach(function(k){
 if(k.classList.contains('tools'))return; var h=k.getBoundingClientRect().height;
 if(k.classList.contains('charts')||k.classList.contains('figures')||k.querySelector('img,.chart,.figure')){charts+=h;n++;}else tools+=h;});}
out.push('ROW|'+i+'|'+name+'|'+Math.round(lt)+'|'+Math.round(tools)+'|'+Math.round(charts)+'|'+n);});
var W=document.documentElement.clientWidth;
document.querySelectorAll('.block').forEach(function(b){var h3=b.querySelector(':scope > h3'); if(!h3) return; if(b.closest('.briefrow')) return; if(b.querySelector('form.runform')) return; var r=b.getBoundingClientRect(); if(r.height<5) return;
 out.push('BLK|'+h3.textContent.trim().slice(0,22)+'|'+Math.round(r.width*100/W));});
var pics=0; document.querySelectorAll('.charts, .interactive-block').forEach(function(c){ if(!c.closest('[id^=figures-]') && !c.closest('.briefrow')) pics++; });
out.push('PICS|'+pics);
var b=document.createElement('div');b.id='rowprobe';b.style.display='none';b.textContent=out.join('\\n');document.body.appendChild(b);});</script>"""
client=app.test_client(); bad=0
BAN=[r'\blearner',r'(?<![_-])estimator',r'(?<![_-])sweep',r'bar size',r'\bzoo\b',r'hyperparam']
for page in ["","A1","A2","B1","B2","C1","C2"]:
    path="/" if not page else f"/card/{page}"
    html=client.get(path).get_data(as_text=True)
    t=re.sub(r'<[^>]+>',' ',re.sub(r'<script.*?</script>','',html,flags=re.S))
    words={w:len(re.findall(w,t,flags=re.I)) for w in BAN}; words={k:v for k,v in words.items() if v}
    longlab=[l.strip() for l in re.findall(r'<label[^>]*>(.*?)</label>',html,flags=re.S) if len(re.sub(r'\([^)]*\)','',re.sub(r'<[^>]+>','',l)).split())>5]
    codes=html.count('<h3>Code</h3>')
    vis=re.sub(r'<[^>]+>',' ',re.sub(r'<(script|style).*?</\1>|<div class="cmd"[^>]*>.*?</div>|<div class="block" id="(?:workflowcode|runcode)".*?</div>','',html,flags=re.S))
    paths=re.findall(r'\b[\w./-]+\.(?:py|sh|parquet)\b',vis)
    codetags=len(re.findall(r'<code>',re.sub(r'<div class="block" id="(?:workflowcode|runcode)".*?</div>','',html,flags=re.S)))
    # a title followed by a paragraph that is not the one note line a tool is allowed
    pairs=[re.sub('<[^>]+>','',m.group(2)).strip()[:30] for m in re.finditer(r'<h([2-5])[^>]*>([^<]*)</h\1>\s*<p\b(?![^>]*(?:hidden|class="note|class="resultline|class="resultdetail))[^>]*>(?!\s*</p>)',html.split('</header>',1)[-1] if page else '',flags=re.S)]
    print(f"== {page or 'front'}  banned={words or 'none'} code-blocks={codes} code-tags={codetags} long-labels={len(longlab)} paths={paths[:4] or 'none'} title+paragraph={pairs or 'none'}")
    if words or codes or longlab or paths or codetags or pairs: bad+=1
    for l in longlab[:5]: print("   long label:",re.sub(r'<[^>]+>','',l)[:80])
    tmp=ce.freeze_page(client,path,probe=PROBE,images=True)
    if page:
        dom=subprocess.run([ce.CHROME,"--headless=new","--disable-gpu","--hide-scrollbars","--window-size=1900,1000","--virtual-time-budget=4000","--dump-dom",tmp.as_uri()],capture_output=True,text=True,timeout=400).stdout
        m=re.search(r'<div id="rowprobe"[^>]*>(.*?)</div>',dom,flags=re.S)
        narrow=[]; pics=None
        for line in (m.group(1).strip().splitlines() if m else ["ROW|?|probe missing|0|0|0|0"]):
            if line.startswith("BLK|"):
                _,t,w=line.split("|")
                if int(w)<90: narrow.append(f"{t} {w}%")
                continue
            if line.startswith("PICS|"): pics=int(line.split("|")[1]); continue
            _,i,name,lt,tools,charts,n=line.split("|"); lt,tools,charts,n=map(int,(lt,tools,charts,n))
            v="ok" if not n else ("ok, charts under tools" if tools<lt else "VIOLATION"); bad+=v=="VIOLATION"
            print(f"   {name:<28} table {lt:>4} tools {tools:>4} charts {charts:>4} ({n}) {v}")
        if narrow or pics: bad+=1
        print(f"   foot blocks under 90% width: {narrow or 'none'} | picture blocks outside Figures: {pics}")
    subprocess.run([ce.CHROME,"--headless=new","--disable-gpu","--hide-scrollbars","--force-device-scale-factor=0.7","--window-size=1900,1400","--virtual-time-budget=4000",f"--screenshot={S}/audit-{page or 'index'}.png",tmp.as_uri()],capture_output=True,timeout=400)
print("problems:",bad)
# export scan: the file the operator opens without a server
xh=pathlib.Path("01-dashboard/control-centre.html").read_text(encoding="utf-8")
xb=re.sub(r'<(script|style).*?</\1>','',xh,flags=re.S); xt=re.sub(r'<[^>]+>',' ',xb)
xw={w:len(re.findall(w,xt,flags=re.I)) for w in BAN}; xw={k:v for k,v in xw.items() if v}
print(f"== export banned={xw or 'none'} code-tags={len(re.findall(r'<code>',xb))} code-blocks={xh.count('<h3>Code</h3>')} panels={xh.count('class=\"panelsheet')} rows={xh.count('class=\"briefrow')} filled-notes={xh.count('optnotes\">')}")
# export row probe: reveal the panels container and measure the same rows
XP="""<script>window.addEventListener('load',function(){var out=[];var P=document.getElementById('panels'); if(P){P.style.display='block';}
document.querySelectorAll('.panelsec,.panelsheet').forEach(function(p){p.hidden=false;p.style.display='block';});
document.querySelectorAll('.briefrow').forEach(function(row,i){var left=row.children[0],right=row.children[1];
var h3=row.querySelector('h3');var name=h3?h3.textContent.trim().slice(0,28):'?';
var lt=left?left.getBoundingClientRect().height:0; var tools=0,charts=0,n=0;
if(right){Array.from(right.querySelectorAll(':scope > *, :scope > .tools > *')).forEach(function(k){
 if(k.classList.contains('tools'))return; var h=k.getBoundingClientRect().height;
 if(k.classList.contains('charts')||k.classList.contains('figures')||k.querySelector('img,.chart,.figure')){charts+=h;n++;}else tools+=h;});}
out.push('ROW|'+i+'|'+name+'|'+Math.round(lt)+'|'+Math.round(tools)+'|'+Math.round(charts)+'|'+n);});
var W=document.documentElement.clientWidth;
document.querySelectorAll('.panelsheet .block').forEach(function(b){var h3=b.querySelector(':scope > h3'); if(!h3) return; if(b.closest('.briefrow')) return; if(b.querySelector('form.runform')) return; var r=b.getBoundingClientRect(); if(r.height<5) return; if(h3.textContent.trim().indexOf('Choose')==0) return;
 out.push('BLK|'+h3.textContent.trim().slice(0,22)+'|'+Math.round(r.width*100/W));});
var b=document.createElement('div');b.id='rowprobe';b.style.display='none';b.textContent=out.join('\\n');document.body.appendChild(b);});</script>"""
xt=S/"export-probe.html"; xt.write_text(xh.replace("</body>",XP+"</body>"),encoding="utf-8")
dom=subprocess.run([ce.CHROME,"--headless=new","--disable-gpu","--hide-scrollbars","--window-size=1900,1000","--virtual-time-budget=8000","--dump-dom",xt.as_uri()],capture_output=True,text=True,timeout=400).stdout
m=re.search(r'<div id="rowprobe"[^>]*>(.*?)</div>',dom,flags=re.S); xbad=0; narrow=[]
for line in (m.group(1).strip().splitlines() if m else []):
    f=line.split("|")
    if f[0]=="ROW":
        lt,tools,charts,n=map(int,f[3:7]); v="ok" if not n else ("ok, charts under tools" if tools<lt else "VIOLATION"); xbad+=v=="VIOLATION"
        if v!="ok": print(f"   export {f[2]:<28} table {lt:>4} tools {tools:>4} charts {charts:>4} ({n}) {v}")
    else:
        if int(f[2])<90: narrow.append(f"{f[1]} {f[2]}%")
print("export rows measured:",sum(1 for l in (m.group(1).strip().splitlines() if m else []) if l.startswith('ROW')),"violations:",xbad,"| blocks after rows under 90% width:",narrow or "none")
