"""Shared real-worker lifecycle and allocation observation for local file probes."""

def prepare_worker_probe(browser,url):
    page = browser.new_page()
    requests=[]
    page.on('request',lambda request: requests.append((request.method,request.url)))
    # Observe real export calls; wrappers preserve the actual WASM return values.
    def observe_allocations(route):
        response=route.fetch()
        prefix="""const fileProbeInstantiate=WebAssembly.instantiate;
        WebAssembly.instantiate=async (...args)=>{
          const instance=await fileProbeInstantiate(...args),exports={...instance.exports};
          for(const name of ['local_battery_limit','local_battery_alloc','local_state_limit','local_state_alloc']) {
            exports[name]=(...args)=>{const result=instance.exports[name](...args);postMessage({type:'abi-proof',name,args,result});return result};
          }
          return {exports};
        };
"""
        route.fulfill(response=response,body=prefix+response.text())
    page.route('**/worker-*.js',observe_allocations)
    page.goto(url)
    page.add_script_tag(content='''window.runWorkerProbe=async (workerPath,action)=>{
      const ensure=(condition,message)=>{if(!condition)throw Error(message)};
      const digest=async bytes=>new Uint8Array(await crypto.subtle.digest('SHA-256',bytes));
      const equal=(a,b)=>a.length===b.length && a.every((x,i)=>x===b[i]);
      const workers=[];
      const create=()=>{const worker=new Worker(workerPath,{type:'module'});workers.push(worker);worker.proof=[];return worker};
      const ask=(worker,data)=>new Promise((resolve,reject)=>{
        const timeout=setTimeout(()=>{worker.terminate();reject(Error('worker response timeout'))},10000);
        worker.onmessage=({data})=>{if(data.type==='abi-proof'){worker.proof.push(data);return}clearTimeout(timeout);resolve(data)};
        worker.onerror=event=>{clearTimeout(timeout);reject(Error(event.message))};worker.postMessage(data);
      });
try {return await action({ensure,digest,equal,create,ask})} finally {workers.forEach(worker=>worker.terminate())}
};''')
    return page,requests


def finish_worker_probe(page,requests,url,result):
    assert all(method=='GET' and target.startswith(url) for method,target in requests),requests
    result['requests']=requests
    page.close()
    return result
