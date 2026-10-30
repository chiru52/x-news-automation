// Client-side authentication is disabled unless an explicit per-product public config is deployed.
// Never put service_role or secret keys in a browser configuration.
const $=id=>document.getElementById(id);
const status=$("auth-status"),form=$("auth-form"),submit=$("auth-submit");
let client=null,mode="sign-in",recoveryAuthorized=false;
const cleanMode=()=>["sign-in","sign-up","forgot","update-password"].includes(location.hash.slice(1))?location.hash.slice(1):"sign-in";
function message(value){status.textContent=value;}
function showMode(){
  mode=cleanMode();
  const headings={"sign-in":"Sign in to SignalDesk","sign-up":"Create a SignalDesk account",forgot:"Reset your password","update-password":"Choose a new password"};
  $("account-heading").textContent=headings[mode];
  $("password-label").hidden=mode==="forgot";
  $("auth-password").hidden=mode==="forgot";
  $("auth-password").required=mode!=="forgot";
  $("auth-password").autocomplete=mode==="sign-in"?"current-password":"new-password";
  $("auth-email").previousElementSibling.hidden=mode==="update-password";
  $("auth-email").hidden=mode==="update-password";
  $("auth-email").required=mode!=="update-password";
  submit.textContent={"sign-in":"Sign in","sign-up":"Create account",forgot:"Email reset link","update-password":"Update password"}[mode];
  for(const name of ["sign-in","sign-up","forgot"]){
    $("account-"+(name==="forgot"?"recover":name)).setAttribute("aria-current",name===mode?"page":"false");
  }
  if(client) form.hidden=!$("account-signed-in").hidden && !(mode==="update-password" && recoveryAuthorized);
  if(mode==="update-password" && !recoveryAuthorized){form.hidden=true;message("Use your password-reset email link to update your password.");}
}
async function setup(){
  try{
    const response=await fetch("./auth-config.json?auth=84",{cache:"no-store"});
    if(!response.ok) throw Error("Config unavailable");
    const config=await response.json();
    if(config.enabled!==true) throw Error("Accounts are not enabled yet.");
    const u=new URL(config.supabase_url);
    if(u.protocol!=="https:" || !/^[a-z0-9-]+\.supabase\.co$/.test(u.hostname) || u.pathname!=="/" ||
       typeof config.publishable_key!=="string" || !config.publishable_key.startsWith("sb_publishable_"))
      throw Error("Invalid account configuration");
    const {createClient}=await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.102.0/+esm");
    client=createClient(u.href,config.publishable_key,{auth:{detectSessionInUrl:true,flowType:"pkce",persistSession:true,autoRefreshToken:true}});
    client.auth.onAuthStateChange((event,session)=>{
      if(event==="PASSWORD_RECOVERY"){recoveryAuthorized=true;location.hash="update-password";showMode();}
      const user=session?.user;
      $("account-signed-in").hidden=!user;
      if(user){$("account-email").textContent="Signed in as "+(user.email||"account");form.hidden=!(mode==="update-password" && recoveryAuthorized);if(mode!=="update-password")message("Your account is active.");}
      else {form.hidden=mode==="update-password";}
    });
    const {data:{user}}=await client.auth.getUser();
    $("account-signed-in").hidden=!user;
    if(user){$("account-email").textContent="Signed in as "+(user.email||"account");form.hidden=!(mode==="update-password" && recoveryAuthorized);if(mode!=="update-password")message("Your account is active.");}
    else {message("Sign in, register, or reset your password.");form.hidden=mode==="update-password";}
    showMode();
  }catch(err){client=null;form.hidden=true;message(err?.message==="Accounts are not enabled yet."?"Accounts are not enabled yet. Continue browsing SignalDesk as a guest.":"Account connection unavailable. Please refresh or try again later; news remains available without signing in.");}
}
addEventListener("hashchange",showMode);
form.addEventListener("submit",async event=>{
  event.preventDefault();if(!client || (mode==="update-password" && !recoveryAuthorized))return;
  submit.disabled=true;message("Processing account request…");
  const email=$("auth-email").value.trim(),password=$("auth-password").value;
  try{
    let response;
    if(mode==="sign-in")response=await client.auth.signInWithPassword({email,password});
    if(mode==="sign-up")response=await client.auth.signUp({email,password,options:{emailRedirectTo:location.origin+location.pathname+"#sign-in"}});
    if(mode==="forgot")response=await client.auth.resetPasswordForEmail(email,{redirectTo:location.origin+location.pathname+"#update-password"});
    if(mode==="update-password")response=await client.auth.updateUser({password});
    if(response?.error)throw response.error;
    message(mode==="sign-up"?"If confirmation is required, check your email to complete registration.":mode==="forgot"?"If the address has an account, you will receive a reset email.":mode==="update-password"?"Password updated.":"Signed in.");
    $("auth-password").value="";
    if(mode==="update-password"){recoveryAuthorized=false;location.hash="sign-in";showMode();}
  }catch(err){message(err?.message||"Account request failed.");}
  finally{submit.disabled=false;}
});
$("account-sign-out").addEventListener("click",async()=>{if(!client)return;const {error}=await client.auth.signOut();if(error){message(error.message);return;}recoveryAuthorized=false;message("Signed out.");$("account-signed-in").hidden=true;location.hash="sign-in";showMode();});
showMode();setup();
