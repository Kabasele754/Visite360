(function(){"use strict";window.TWINSCOPE_COMMERCE_UI_VERSION="cart-state-v3-20260717";
const money=(currency,value)=>`${currency} ${Number(value||0).toFixed(2)}`;
function safeBack(){if(document.referrer&&new URL(document.referrer,location.href).origin===location.origin){history.back();}else{location.href="/products/";}}
document.querySelectorAll("[data-market-back]").forEach(btn=>btn.addEventListener("click",safeBack));

async function updateCart(form,input){
 const row=form.closest("[data-cart-row]"); const body=new FormData(form);
 try{
  const response=await fetch(form.action,{method:"POST",body,headers:{"X-Requested-With":"XMLHttpRequest"},credentials:"same-origin"});
  if(!response.ok) throw new Error(`HTTP ${response.status}`);
  const data=await response.json();
  if(data.removed){row?.remove();}
  else{
   input.value=data.quantity;
   input.max=data.max_quantity;
   row?.querySelector("[data-line-total]")?.replaceChildren(document.createTextNode(money(data.currency,data.line_total)));
   row?.querySelector("[data-cart-minus]")?.toggleAttribute("disabled",data.quantity<=1);
   row?.querySelector("[data-cart-plus]")?.toggleAttribute("disabled",data.quantity>=data.max_quantity);
  }
  const subtotal=document.querySelector("[data-cart-subtotal]");
  if(subtotal) subtotal.textContent=money(data.currency,data.subtotal);
  document.querySelectorAll("[data-cart-count]").forEach(el=>{
      el.textContent=data.count;
      el.hidden=Number(data.count||0)<=0;
    });
 }catch(error){console.error("CART_UPDATE_FAILED",error); form.requestSubmit();}
}
document.querySelectorAll("[data-cart-quantity]").forEach(form=>{
 const input=form.querySelector("input[name='quantity']"); if(!input)return; let timer;
 const commit=()=>{clearTimeout(timer);timer=setTimeout(()=>updateCart(form,input),120)};
 const syncButtons=()=>{const value=Number(input.value||1),max=Number(input.max||99);form.querySelector("[data-cart-minus]")?.toggleAttribute("disabled",value<=1);form.querySelector("[data-cart-plus]")?.toggleAttribute("disabled",value>=max)};
 form.querySelector("[data-cart-minus]")?.addEventListener("click",()=>{input.value=Math.max(1,Number(input.value||1)-1);syncButtons();commit()});
 form.querySelector("[data-cart-plus]")?.addEventListener("click",()=>{const max=Number(input.max||99);input.value=Math.min(max,Number(input.value||1)+1);syncButtons();commit()});
 input.addEventListener("change",()=>{const max=Number(input.max||99);input.value=Math.max(1,Math.min(max,Number(input.value||1)));syncButtons();commit()});syncButtons();
});

const fulfillment=document.querySelector("[name='fulfillment']");function syncDelivery(){const delivery=fulfillment?.value==="delivery";document.querySelectorAll("[data-delivery-only]").forEach(field=>{field.hidden=!delivery;field.querySelectorAll("input,select,textarea").forEach(el=>el.disabled=!delivery)})}fulfillment?.addEventListener("change",syncDelivery);syncDelivery();

function showCartToast(message, cartUrl){
 let toast=document.getElementById("marketCartToast");
 if(!toast){
  toast=document.createElement("div");toast.id="marketCartToast";toast.className="market-cart-toast";
  toast.innerHTML='<span data-cart-toast-message></span><a data-cart-toast-link href="/cart/">View cart</a>';
  document.body.appendChild(toast);
 }
 toast.querySelector("[data-cart-toast-message]").textContent=message||"Added to cart.";
 if(cartUrl)toast.querySelector("[data-cart-toast-link]").href=cartUrl;
 toast.classList.add("is-visible");clearTimeout(toast._timer);
 toast._timer=setTimeout(()=>toast.classList.remove("is-visible"),3200);
}
document.addEventListener("submit",async event=>{
 const form=event.target.closest?.("[data-product-cart-form]");if(!form)return;
 event.preventDefault();
 const button=form.querySelector("button[type='submit']");if(!button||button.disabled)return;
 button.classList.add("is-loading");button.setAttribute("aria-busy","true");
 try{
  const response=await fetch(form.action,{method:"POST",body:new FormData(form),headers:{"X-Requested-With":"XMLHttpRequest"},credentials:"same-origin"});
  const data=await response.json();
  if(!response.ok||!data.ok)throw new Error(data.error||"Could not add this product.");
  document.querySelectorAll("[data-cart-count]").forEach(el=>{
      el.textContent=data.count;
      el.hidden=Number(data.count||0)<=0;
    });
  const card=form.closest("[data-product-card]");
  if(card){
    card.classList.add("is-in-cart");
    card.dataset.cartState="in-cart";
    const badge=card.querySelector("[data-product-cart-badge]");
    if(badge){badge.hidden=false;badge.textContent=`In cart · ${data.quantity || 1}`;}
    const icon=card.querySelector("[data-cart-button-icon]");
    if(icon)icon.textContent="✓";
    button.classList.add("is-in-cart");
  }
  showCartToast(data.message,data.cart_url);
  button.classList.add("is-added");
  const old=button.getAttribute("aria-label");button.setAttribute("aria-label","Added to cart");
  setTimeout(()=>{button.classList.remove("is-added");if(old)button.setAttribute("aria-label",old)},1200);
 }catch(error){
  console.error("CART_ADD_FAILED",error);
  showCartToast(error.message||"Could not add this product.");
 }finally{
  button.classList.remove("is-loading");button.removeAttribute("aria-busy");
 }
});

const grid=document.getElementById("marketProductGrid"),sentinel=document.getElementById("marketProductSentinel");let loading=false;
async function loadMore(){if(!grid||!sentinel||loading||grid.dataset.hasNext!=="true")return;loading=true;sentinel.classList.add("is-loading");try{const url=new URL(location.href);url.searchParams.set("page",grid.dataset.nextPage);url.searchParams.set("format","json");const response=await fetch(url,{headers:{"X-Requested-With":"XMLHttpRequest"}});if(!response.ok)throw new Error(`HTTP ${response.status}`);const data=await response.json();grid.insertAdjacentHTML("beforeend",data.html);grid.dataset.hasNext=String(data.has_next);grid.dataset.nextPage=data.next_page||"";sentinel.hidden=!data.has_next;}catch(error){console.error("PRODUCT_INFINITE_SCROLL_FAILED",error);sentinel.hidden=true;}finally{loading=false;sentinel.classList.remove("is-loading")}}
if(grid&&sentinel&&"IntersectionObserver" in window){new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting))loadMore()},{rootMargin:"700px 0px"}).observe(sentinel)}
})();

/* Marketplace bottom search/filter sheet */
(()=>{
 const sheet=document.getElementById("marketProductFilterSheet");
 const backdrop=document.getElementById("marketProductFilterBackdrop");
 if(!sheet)return;
 let lastTrigger=null;
 const open=trigger=>{lastTrigger=trigger||document.activeElement;backdrop.hidden=false;requestAnimationFrame(()=>{backdrop.classList.add("is-open");sheet.removeAttribute("inert");sheet.setAttribute("aria-hidden","false");sheet.classList.add("is-open");document.body.classList.add("market-filter-open");requestAnimationFrame(()=>sheet.querySelector("input,select")?.focus({preventScroll:true}));});};
 const close=()=>{const focused=document.activeElement;if(focused&&sheet.contains(focused))focused.blur();sheet.classList.remove("is-open");backdrop.classList.remove("is-open");sheet.setAttribute("aria-hidden","true");sheet.setAttribute("inert","");document.body.classList.remove("market-filter-open");setTimeout(()=>{backdrop.hidden=true;if(lastTrigger&&document.contains(lastTrigger))lastTrigger.focus({preventScroll:true});},240);};
 document.querySelectorAll("[data-market-filter-open]").forEach(btn=>btn.addEventListener("click",()=>open(btn)));
 document.querySelectorAll("[data-market-filter-close]").forEach(btn=>btn.addEventListener("click",close));
 addEventListener("keydown",e=>{if(e.key==="Escape"&&sheet.classList.contains("is-open"))close();});
})();
