async function fetchStates(){
    const res = await fetch("/home_map/state");
    const data = await res.json();
    data.devices.forEach(dev=>{
        const el = document.querySelector(`.device[data-id='${dev.id}']`);
        if(el) el.style.backgroundColor = dev.state=="on" ? "yellow" : "gray";
    });
}

// تحديث كل 5 ثواني
setInterval(fetchStates, 5000);
fetchStates();

// التبديل عند الضغط
document.querySelectorAll(".device").forEach(el=>{
    el.addEventListener("click", async ()=>{
        const eid = el.dataset.id;
        await fetch("/home_map/toggle", {
            method:"POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify({entity_id:eid})
        });
        fetchStates();
    });
});
