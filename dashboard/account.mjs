// Client-side authentication is disabled unless an explicit per-product public config is deployed.
// Never put service_role or secret keys in a browser configuration.
const $=id=>document.getElementById(id);
const status=$("auth-status"),form=$("auth-form"),submit=$("auth-submit");
let client=null,mode="sign-in",verifiedUser=false,currentUser=null;
const dashboardUrl="./";
const cleanMode=()=>["sign-in","sign-up","forgot","update-password"].includes(location.hash.slice(1))?location.hash.slice(1):"sign-in";
function message(value){status.textContent=value;}
function showMode(){
  mode=cleanMode();
  const headings={"sign-in":"Sign in to SignalDesk","sign-up":"Create a SignalDesk account",forgot:"Reset your password","update-password":"Choose a new password"};
  $("account-heading").textContent=headings[mode];
  $("auth-name-label").hidden=mode!=="sign-up";
  $("auth-name").hidden=mode!=="sign-up";
  $("auth-name").required=mode==="sign-up";
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
  if(client) form.hidden=!$("account-signed-in").hidden && !(mode==="update-password" && verifiedUser);
  document.querySelector(".account-links").hidden=verifiedUser && mode!=="update-password";
  if(mode==="update-password" && !verifiedUser){form.hidden=true;message("Use your password-reset email link to update your password.");}
}
function renderAccountUser(user){
  currentUser=user||null;verifiedUser=!!user;
  $("account-signed-in").hidden=!user;
  document.querySelector(".account-links").hidden=!!user && mode!=="update-password";
  if(!user)return;
  $("account-email").textContent="Signed in as "+(user.email||"account");
  $("account-created").textContent=user.created_at?"Account created: "+new Date(user.created_at).toLocaleDateString():"";
  $("profile-name").value=String(user.user_metadata?.display_name||"").slice(0,80);
}
function settingsMessage(value){$("account-settings-status").textContent=value;}
$("profile-form").addEventListener("submit",async event=>{
  event.preventDefault();if(!client||!currentUser)return;
  const button=event.currentTarget.querySelector("button");button.disabled=true;
  try{
    const display_name=$("profile-name").value.trim();
    const {data,error}=await client.auth.updateUser({data:{display_name}});
    if(error)throw error;
    renderAccountUser(data.user);settingsMessage("Profile saved.");
  }catch(_error){settingsMessage("Could not save profile. Please try again.");}
  finally{button.disabled=false;}
});
$("account-password-form").addEventListener("submit",async event=>{
  event.preventDefault();if(!client||!currentUser)return;
  const button=event.currentTarget.querySelector('button[type="submit"]');
  const current_password=$("account-current-password").value;
  const password=$("account-new-password").value;
  const confirmation=$("account-confirm-password").value;
  if(password.length<6){settingsMessage("New password must contain at least 6 characters.");return;}
  if(password!==confirmation){settingsMessage("New passwords do not match.");return;}
  if(current_password===password){settingsMessage("Choose a different new password.");return;}
  button.disabled=true;settingsMessage("Updating password…");
  try{
    // Supabase Auth validates the current password server-side.
    const {error}=await client.auth.updateUser({password,current_password});
    if(error)throw error;
    $("account-password-form").reset();
    settingsMessage("Password updated successfully.");
  }catch(_error){
    $("account-current-password").value="";
    settingsMessage("Password could not be updated. Check your current password and try again.");
  }finally{button.disabled=false;}
});

async function setup(){
  let phase="configuration";
  try{
    const response=await fetch("./auth-config.json?auth=84",{cache:"no-store"});
    if(!response.ok) throw Error("Config unavailable");
    const config=await response.json();
    if(config.enabled!==true) throw Error("Accounts are not enabled yet.");
    const u=new URL(config.supabase_url);
    if(u.protocol!=="https:" || !/^[a-z0-9-]+\.supabase\.co$/.test(u.hostname) || u.pathname!=="/" ||
       typeof config.publishable_key!=="string" || !config.publishable_key.startsWith("sb_publishable_"))
      throw Error("Invalid account configuration");
    phase="authentication library";
    const {createClient}=await import("https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.102.0/+esm");
    phase="Supabase initialization";
    client=createClient(u.href,config.publishable_key,{auth:{detectSessionInUrl:true,flowType:"pkce",persistSession:true,autoRefreshToken:true}});
    client.auth.onAuthStateChange((event,session)=>{
      if(event==="PASSWORD_RECOVERY"){location.hash="update-password";}
      const user=session?.user;
      renderAccountUser(user);
      if(user){$("account-email").textContent="Signed in as "+(user.email||"account");form.hidden=!(mode==="update-password" && verifiedUser);if(mode!=="update-password")message("Your account is active.");}
      else {form.hidden=mode==="update-password";}
    });
    phase="Supabase session check";
    const {data:{user}}=await client.auth.getUser();
    renderAccountUser(user);
    if(user){$("account-email").textContent="Signed in as "+(user.email||"account");form.hidden=!(mode==="update-password" && verifiedUser);if(mode!=="update-password")message("Your account is active.");}
    else {message("Sign in, register, or reset your password.");form.hidden=mode==="update-password";}
    showMode();
  }catch(err){client=null;form.hidden=true;message(err?.message==="Accounts are not enabled yet."?"Accounts are not enabled yet. Continue browsing SignalDesk as a guest.":"Account connection unavailable ("+phase+"). News remains available without signing in.");}
}
addEventListener("hashchange",showMode);
form.addEventListener("submit",async event=>{
  event.preventDefault();if(!client || (mode==="update-password" && !verifiedUser))return;
  submit.disabled=true;message("Processing account request…");
  const email=$("auth-email").value.trim(),password=$("auth-password").value;
  try{
    let response;
    if(mode==="sign-in")response=await client.auth.signInWithPassword({email,password});
    if(mode==="sign-up")response=await client.auth.signUp({email,password,options:{emailRedirectTo:location.origin+location.pathname+"#sign-in",data:{display_name:$("auth-name").value.trim()}}});
    if(mode==="forgot")response=await client.auth.resetPasswordForEmail(email,{redirectTo:location.origin+location.pathname+"#update-password"});
    if(mode==="update-password")response=await client.auth.updateUser({password});
    if(response?.error)throw response.error;
    message(mode==="sign-up"?"If confirmation is required, check your email to complete registration.":mode==="forgot"?"If the address has an account, you will receive a reset email.":mode==="update-password"?"Password updated.":"Signed in.");
    $("auth-password").value="";
    if(mode==="update-password"){
      const signedOut=await client.auth.signOut();
      if(signedOut.error) throw signedOut.error;
      renderAccountUser(null);
      location.hash="sign-in";showMode();
      message("Password updated successfully. Please sign in with your new password.");
    } else if(mode==="sign-in"){
      location.assign(dashboardUrl);
    }
  }catch(err){message(err?.message||"Account request failed.");}
  finally{submit.disabled=false;}
});
$("account-sign-out").addEventListener("click",async()=>{if(!client)return;const {error}=await client.auth.signOut();if(error){message(error.message);return;}renderAccountUser(null);message("Signed out.");location.hash="sign-in";showMode();});
if(new URLSearchParams(location.search).has("embedded"))document.body.classList.add("account-embedded");
showMode();setup();
