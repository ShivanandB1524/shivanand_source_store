
const API_BASE = "";

const accountOverlay = document.getElementById("accountOverlay");
const accountNavBtn = document.getElementById("accountNavBtn");
const accountNavText = document.getElementById("accountNavText");
const accountClose = document.getElementById("accountClose");
const authView = document.getElementById("authView");
const accountView = document.getElementById("accountView");
const loginForm = document.getElementById("loginForm");
const signupForm = document.getElementById("signupForm");
const accountMessage = document.getElementById("accountMessage");
const purchaseMessage = document.getElementById("purchaseMessage");
let pendingProduct = null;

function getToken(){ return localStorage.getItem("source_store_token"); }

function setMessage(el, msg, ok=false){
  el.textContent = msg || "";
  el.style.color = ok ? "#16a34a" : "#dc2626";
}

function openAccount(mode="login", product=null){
  pendingProduct = product;
  accountOverlay.classList.add("open");
  accountOverlay.setAttribute("aria-hidden","false");
  switchAuthTab(mode);
  if(getToken()) showAccount();
}

function closeAccount(){
  accountOverlay.classList.remove("open");
  accountOverlay.setAttribute("aria-hidden","true");
}

function switchAuthTab(tab){
  document.querySelectorAll(".account-tab").forEach(btn=>{
    btn.classList.toggle("active", btn.dataset.authTab === tab);
  });
  const login = tab === "login";
  loginForm.classList.toggle("hidden", !login);
  signupForm.classList.toggle("hidden", login);
  document.getElementById("accountTitle").textContent = login ? "Welcome back" : "Create your account";
  document.getElementById("accountSubtitle").textContent =
    login ? "Login to access your purchased source code." : "Save your purchases to your personal library.";
  setMessage(accountMessage, "");
}

function showAccount(){
  authView.classList.add("hidden");
  accountView.classList.remove("hidden");
  const cached = JSON.parse(localStorage.getItem("source_store_user") || "{}");
  document.getElementById("profileName").textContent = cached.name || "Account";
  document.getElementById("profilePhone").textContent = cached.phone || "";
  document.getElementById("profileAvatar").textContent = (cached.name || "U").trim().charAt(0).toUpperCase();
  accountNavText.textContent = "My Account";
  loadPurchases();
}

function showAuth(){
  accountView.classList.add("hidden");
  authView.classList.remove("hidden");
  accountNavText.textContent = "Account";
}

async function api(path, options={}){
  const headers = {"Content-Type":"application/json", ...(options.headers || {})};
  const token = getToken();
  if(token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(API_BASE + path, {...options, headers});
  const data = await response.json().catch(()=>({detail:"Unexpected server response"}));
  if(!response.ok) throw new Error(data.detail || "Request failed");
  return data;
}

loginForm.addEventListener("submit", async (e)=>{
  e.preventDefault();
  setMessage(accountMessage, "Logging in…", true);
  try{
    const data = await api("/api/auth/login", {
      method:"POST",
      body:JSON.stringify({
        phone: document.getElementById("loginPhone").value.trim(),
        password: document.getElementById("loginPassword").value
      })
    });
    localStorage.setItem("source_store_token", data.token);
    localStorage.setItem("source_store_user", JSON.stringify(data.user));
    showAccount();
    if(pendingProduct) beginPurchase(pendingProduct);
  }catch(err){ setMessage(accountMessage, err.message); }
});

signupForm.addEventListener("submit", async (e)=>{
  e.preventDefault();
  setMessage(accountMessage, "Creating account…", true);
  try{
    const data = await api("/api/auth/signup", {
      method:"POST",
      body:JSON.stringify({
        name: document.getElementById("signupName").value.trim(),
        phone: document.getElementById("signupPhone").value.trim(),
        password: document.getElementById("signupPassword").value
      })
    });
    localStorage.setItem("source_store_token", data.token);
    localStorage.setItem("source_store_user", JSON.stringify(data.user));
    showAccount();
    if(pendingProduct) beginPurchase(pendingProduct);
  }catch(err){ setMessage(accountMessage, err.message); }
});

document.querySelectorAll(".account-tab").forEach(btn=>{
  btn.addEventListener("click", ()=>switchAuthTab(btn.dataset.authTab));
});

accountNavBtn?.addEventListener("click", ()=>openAccount(getToken() ? "login" : "login"));
accountClose?.addEventListener("click", closeAccount);
accountOverlay?.addEventListener("click", e=>{ if(e.target === accountOverlay) closeAccount(); });
document.addEventListener("keydown", e=>{ if(e.key === "Escape") closeAccount(); });

document.querySelectorAll(".purchase-link").forEach(link=>{
  link.addEventListener("click", (e)=>{
    const product = {
      id: link.dataset.productId,
      name: link.dataset.productName,
      paymentUrl: link.href
    };
    // Keep the existing Razorpay destination. We only require an account before leaving.
    if(!getToken()){
      e.preventDefault();
      openAccount("login", product);
    }else{
      // Store the intended product locally so a backend webhook can later associate the payment.
      localStorage.setItem("pending_product", JSON.stringify(product));
    }
  });
});

function beginPurchase(product){
  localStorage.setItem("pending_product", JSON.stringify(product));
  window.location.href = product.paymentUrl;
}

async function loadPurchases(){
  try{
    const data = await api("/api/purchases");
    const list = document.getElementById("purchaseList");
    if(!data.purchases.length){
      list.innerHTML = `<div class="purchase-empty"><i class="fa-solid fa-box-open"></i><p>No purchases found yet.</p><span>Your verified purchases will appear here.</span></div>`;
      return;
    }
    list.innerHTML = data.purchases.map(p=>`
      <div class="purchase-item">
        <div class="purchase-icon"><i class="fa-solid fa-file-code"></i></div>
        <div class="purchase-info">
          <strong>${escapeHtml(p.product_name)}</strong>
          <span>Purchased ${escapeHtml(p.purchased_at || "")}</span>
        </div>
        <button class="download-btn" data-download="${encodeURIComponent(p.product_id)}">Download</button>
      </div>
    `).join("");
    list.querySelectorAll("[data-download]").forEach(btn=>{
      btn.addEventListener("click", ()=>window.location.href = `/api/purchases/${btn.dataset.download}/download`);
    });
  }catch(err){
    setMessage(purchaseMessage, err.message);
  }
}

document.getElementById("refreshPurchases")?.addEventListener("click", loadPurchases);
document.getElementById("logoutBtn")?.addEventListener("click", ()=>{
  localStorage.removeItem("source_store_token");
  localStorage.removeItem("source_store_user");
  showAuth();
  switchAuthTab("login");
});

function escapeHtml(value){
  return String(value).replace(/[&<>"']/g, m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]));
}

if(getToken()) showAccount();
