(()=>{
  const THEME_KEY="twinscopes-market-theme";
  const legacyThemeKeys=["twinscopesTheme","virtualToursTheme"];
  const root=document.documentElement;

  const readTheme=()=>localStorage.getItem(THEME_KEY)||legacyThemeKeys.map(k=>localStorage.getItem(k)).find(Boolean)||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
  const applyTheme=theme=>{
    const resolved=theme==="dark"?"dark":"light";
    const dark=resolved==="dark";
    root.dataset.marketTheme=resolved;
    root.style.colorScheme=resolved;
    document.body?.classList.toggle("theme-dark",dark);
    document.querySelectorAll("[data-ts-theme-toggle]").forEach(button=>button.setAttribute("aria-pressed",String(dark)));
    localStorage.setItem(THEME_KEY,resolved);
    localStorage.setItem("twinscopesTheme",resolved);
  };

  const getChrome=()=>({
    desktop:document.getElementById("desktopHeader"),
    mobileTop:document.getElementById("mobileTopActions"),
    mobileBottom:document.getElementById("mobileBottomNav")
  });

  let chromeHidden=false;
  const setChromeHidden=(hidden,{force=false}={})=>{
    if(!force&&chromeHidden===hidden)return;
    chromeHidden=hidden;
    const {desktop,mobileTop,mobileBottom}=getChrome();
    [desktop,mobileTop,mobileBottom].forEach(element=>{
      if(!element)return;
      element.classList.toggle("is-scroll-hidden",hidden);
      element.classList.toggle("is-scroll-visible",!hidden);
      element.setAttribute("data-scroll-state",hidden?"hidden":"visible");
    });
    document.body?.classList.toggle("ts-public-chrome-hidden",hidden);
  };

  const closeMore=({restoreFocus=false}={})=>{
    const sheet=document.getElementById("tsMobileMoreSheet");
    const trigger=document.querySelector("[data-ts-more-toggle]");
    if(!sheet)return;
    const focused=document.activeElement;
    if(focused&&sheet.contains(focused)&&typeof focused.blur==="function")focused.blur();
    sheet.classList.remove("is-open");
    sheet.setAttribute("aria-hidden","true");
    sheet.setAttribute("inert","");
    trigger?.setAttribute("aria-expanded","false");
    document.body?.classList.remove("ts-more-open");
    if(restoreFocus&&trigger&&document.contains(trigger))requestAnimationFrame(()=>trigger.focus({preventScroll:true}));
  };

  const initSmartScroll=()=>{
    let lastY=Math.max(0,window.scrollY||0);
    let accumulated=0;
    let ticking=false;
    let ignoreUntil=0;
    const minY=88;
    const hideDelta=18;
    const showDelta=8;

    const shouldKeepVisible=()=>{
      const sheet=document.getElementById("tsMobileMoreSheet");
      const active=document.activeElement;
      return Boolean(
        sheet?.classList.contains("is-open")||
        document.body?.classList.contains("modal-open")||
        document.body?.classList.contains("search-open")||
        active?.matches?.("input,textarea,select,[contenteditable='true']")
      );
    };

    const update=()=>{
      ticking=false;
      const y=Math.max(0,window.scrollY||document.documentElement.scrollTop||0);
      const delta=y-lastY;
      const desktop=document.getElementById("desktopHeader");
      desktop?.classList.toggle("is-scrolled",y>18);

      if(Date.now()<ignoreUntil||shouldKeepVisible()||y<=minY){
        accumulated=0;
        setChromeHidden(false);
        lastY=y;
        return;
      }

      if(Math.sign(delta)!==Math.sign(accumulated))accumulated=0;
      accumulated+=delta;

      if(accumulated>=hideDelta){
        setChromeHidden(true);
        accumulated=0;
      }else if(accumulated<=-showDelta){
        setChromeHidden(false);
        accumulated=0;
      }
      lastY=y;
    };

    addEventListener("scroll",()=>{
      if(!ticking){ticking=true;requestAnimationFrame(update)}
    },{passive:true});
    addEventListener("resize",()=>{ignoreUntil=Date.now()+220;setChromeHidden(false,{force:true});lastY=Math.max(0,scrollY||0)},{passive:true});
    addEventListener("pageshow",()=>setChromeHidden(false,{force:true}));
    document.addEventListener("focusin",event=>{
      if(event.target?.matches?.("input,textarea,select,[contenteditable='true']"))setChromeHidden(false);
    });
    setChromeHidden(false,{force:true});
  };

  applyTheme(readTheme());
  addEventListener("DOMContentLoaded",()=>{
    applyTheme(readTheme());
    document.querySelectorAll("[data-ts-theme-toggle]").forEach(button=>button.addEventListener("click",()=>applyTheme(root.dataset.marketTheme==="dark"?"light":"dark")));

    const sheet=document.getElementById("tsMobileMoreSheet");
    const trigger=document.querySelector("[data-ts-more-toggle]");
    trigger?.addEventListener("click",()=>{
      if(!sheet)return;
      const open=!sheet.classList.contains("is-open");
      if(!open){closeMore({restoreFocus:true});return}
      setChromeHidden(false);
      sheet.removeAttribute("inert");
      sheet.setAttribute("aria-hidden","false");
      sheet.classList.add("is-open");
      trigger.setAttribute("aria-expanded","true");
      document.body?.classList.add("ts-more-open");
    });
    document.querySelectorAll("[data-ts-more-close]").forEach(button=>button.addEventListener("click",()=>closeMore({restoreFocus:true})));
    sheet?.querySelectorAll("a").forEach(anchor=>anchor.addEventListener("click",()=>closeMore()));
    addEventListener("keydown",event=>{if(event.key==="Escape")closeMore({restoreFocus:true})});
    initSmartScroll();
  });
})();
