(() => {
  if ("serviceWorker" in navigator) {
    addEventListener("load", () => navigator.serviceWorker.register("/service-worker.js").catch(() => {}));
  }

  const endpoint = "/api/performance/web-vitals/";
  const send = metric => {
    const body = JSON.stringify({
      name: metric.name,
      value: metric.value,
      rating: metric.rating || "",
      path: location.pathname,
      navigationType: performance.getEntriesByType("navigation")[0]?.type || "",
      device: matchMedia("(max-width:768px)").matches ? "mobile" : "desktop",
    });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(endpoint, new Blob([body], {type:"application/json"}));
    } else {
      fetch(endpoint, {method:"POST",headers:{"Content-Type":"application/json"},body,keepalive:true}).catch(()=>{});
    }
  };

  try {
    new PerformanceObserver(list => {
      const entries = list.getEntries();
      const last = entries[entries.length - 1];
      if (last) send({name:"LCP", value:last.startTime, rating:""});
    }).observe({type:"largest-contentful-paint", buffered:true});
  } catch (_) {}

  try {
    let cls = 0;
    new PerformanceObserver(list => {
      for (const entry of list.getEntries()) if (!entry.hadRecentInput) cls += entry.value;
      send({name:"CLS", value:cls, rating:""});
    }).observe({type:"layout-shift", buffered:true});
  } catch (_) {}
})();
