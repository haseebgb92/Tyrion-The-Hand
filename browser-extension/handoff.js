"use strict";
// A one-shot, user-enabled submit helper for extension-created Tyrion handoff tabs.
// It only observes the current prompt composer; never reads ChatGPT responses.
(async()=>{
  const url=new URL(location.href);
  const nonce=url.searchParams.get("tyrion_auto");
  if(!nonce||!/^[a-f0-9]{32}$/.test(nonce))return;
  if(location.origin!=="https://chatgpt.com")return;

  function signal(type,params={}){
    return new Promise((resolve,reject)=>{
      chrome.runtime.sendMessage({type,nonce,...params},response=>{
        if(chrome.runtime.lastError)return reject(Error(chrome.runtime.lastError.message));
        if(!response?.ok)return reject(Error(response?.error||"Tyrion connection unavailable"));
        resolve(response.result);
      });
    });
  }
  const until=Date.now()+25000;
  while(Date.now()<until){
    const editor=document.querySelector('div.ProseMirror[contenteditable="true"], [role="textbox"][contenteditable="true"]');
    if(editor && editor.innerText.trim()){
      // The extension verifies that its own generic task-ID prompt is present.
      // A user-edited composer is never automatically submitted.
      const current=editor.innerText.replace(/\s+/g," ").trim();
      const expected=url.searchParams.get("q")?.replace(/\s+/g," ").trim();
      if(!expected||current!==expected)return;
      const sendButton=document.querySelector('button[data-testid="send-button"],button[aria-label="Send"],button[aria-label="Send prompt"]');
      if(sendButton && !sendButton.disabled){
        try{
          const authorization=await signal("authorizeAutoSubmit");
          if(current!==authorization.expectedPrompt.replace(/\s+/g," ").trim() ||
             editor.innerText.replace(/\s+/g," ").trim()!==current || sendButton.disabled)return;
          // Single click only, no retries, no Stop/Regenerate or output capture.
          sendButton.click();
          await signal("reportAutoSubmit",{clicked:true});
        }catch(error){
          try{await signal("reportAutoSubmit",{clicked:false})}catch{}
        }
        return;
      }
    }
    await new Promise(resolve=>setTimeout(resolve,250));
  }
})();
