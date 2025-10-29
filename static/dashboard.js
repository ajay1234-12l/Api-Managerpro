// dashboard.js - handles listing, create, update, delete, check, auto-refresh
document.addEventListener("DOMContentLoaded", function() {
  const tbody = document.getElementById("keysTbody");
  const searchBox = document.getElementById("searchBox");
  const modal = new bootstrap.Modal(document.getElementById("modalKey"), {});
  const formKey = document.getElementById("formKey");
  const modalTitle = document.getElementById("modalTitle");
  const modalMode = document.getElementById("modalMode");

  async function fetchKeysAndRender() {
    tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4">Loading...</td></tr>`;
    const res = await fetch("/api/keys");
    if (res.status !== 200) {
      const j = await res.json();
      tbody.innerHTML = `<tr><td colspan="5" class="text-danger py-4">Error: ${j.error || 'Failed to fetch'}</td></tr>`;
      return;
    }
    const j = await res.json();
    const keys = j.keys || [];
    renderTable(keys);
  }

  function renderTable(keys) {
    const q = (searchBox.value || "").toLowerCase().trim();
    const rows = keys.filter(k => {
      const kk = (k.key||"").toString().toLowerCase();
      return kk.includes(q);
    }).map(k => {
      const key = k.key || JSON.stringify(k.raw).slice(0,40);
      const remaining = (k.remaining!==null && k.remaining!==undefined) ? k.remaining : "";
      const total = (k.total!==null && k.total!==undefined) ? k.total : "";
      const req = (remaining!=="" || total!=="") ? `${remaining}/${total}` : "";
      const expires = k.expires_at || "";
      let daysLeft = "";
      if (expires) {
        // try to compute days left in JS
        let d = new Date(expires);
        if (!isNaN(d)) {
          const diff = Math.ceil((d - new Date())/(1000*60*60*24));
          daysLeft = diff > 0 ? diff + " days" : "0 days";
        }
      }
      return `<tr>
        <td style="word-break:break-all">${escapeHtml(key)}</td>
        <td>${escapeHtml(req)}</td>
        <td>${escapeHtml(expires)}</td>
        <td>${escapeHtml(daysLeft)}</td>
        <td>
          <button class="btn btn-sm btn-info me-1" onclick="checkKey('${escapeJs(key)}')">Check</button>
          <button class="btn btn-sm btn-warning me-1" onclick="openEdit('${escapeJs(key)}', ${remaining||0}, ${total||0}, '${escapeJs(expires)}')">Edit</button>
          <button class="btn btn-sm btn-danger" onclick="deleteKey('${escapeJs(key)}')">Delete</button>
        </td>
      </tr>`;
    }).join("") || `<tr><td colspan="5" class="text-center py-4">No keys found</td></tr>`;

    tbody.innerHTML = rows;
  }

  // helpers to escape
  window.escapeHtml = function (s) {
    if (s===null || s===undefined) return "";
    return String(s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});
  }
  window.escapeJs = function(s){
    if (s===null||s===undefined) return "";
    return String(s).replace(/'/g,"\\'");
  }

  // open create modal
  document.getElementById("btnCreate").addEventListener("click", function(){
    modalTitle.innerText = "Create Key";
    modalMode.value = "create";
    formKey.reset();
    modal.show();
  });

  window.openEdit = function(key, remaining, total, expires) {
    modalTitle.innerText = "Update Key - " + key;
    modalMode.value = "update";
    document.getElementById("custom_key").value = key;
    document.getElementById("total_requests").value = total || "";
    document.getElementById("expiry_days").value = ""; // leave blank if not changing
    document.getElementById("notes").value = "";
    modal.show();
  }

  formKey.addEventListener("submit", async function(e){
    e.preventDefault();
    const mode = modalMode.value;
    const custom_key = document.getElementById("custom_key").value.trim() || null;
    const total_requests = document.getElementById("total_requests").value.trim() || null;
    const expiry_days = document.getElementById("expiry_days").value.trim() || null;
    const notes = document.getElementById("notes").value.trim() || "";

    if (mode === "create") {
      // POST /api/key/create
      const payload = { custom_key, total_requests: total_requests?parseInt(total_requests):undefined, expiry_days: expiry_days?parseInt(expiry_days):undefined, notes };
      const r = await fetch("/api/key/create", {
        method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload)
      });
      const jr = await r.json();
      if (r.status === 200) {
        Swal.fire("Created","Key created successfully","success");
        modal.hide();
        fetchKeysAndRender();
      } else {
        Swal.fire("Error", jr.error || JSON.stringify(jr), "error");
      }
    } else {
      // update - our API wrapper expects JSON with 'key' and update fields
      const key = custom_key;
      const payload = { key };
      if (total_requests) payload["total_requests"] = parseInt(total_requests);
      if (expiry_days) payload["expiry_days"] = parseInt(expiry_days);
      payload["notes"] = notes;
      const r = await fetch("/api/key/update", {
        method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload)
      });
      const jr = await r.json();
      if (r.status === 200) {
        Swal.fire("Updated","Key updated successfully","success");
        modal.hide();
        fetchKeysAndRender();
      } else {
        Swal.fire("Error", jr.error || JSON.stringify(jr), "error");
      }
    }
  });

  window.deleteKey = async function(key) {
    Swal.fire({
      title: 'Delete key?',
      text: key,
      icon: 'warning',
      showCancelButton: true,
      confirmButtonText: 'Delete'
    }).then(async (res) => {
      if (!res.isConfirmed) return;
      const r = await fetch("/api/key/delete", {
        method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify({ key })
      });
      const jr = await r.json();
      if (r.status === 200) {
        Swal.fire("Deleted","Key deleted","success");
        fetchKeysAndRender();
      } else {
        Swal.fire("Error", jr.error || JSON.stringify(jr), "error");
      }
    });
  }

  window.checkKey = async function(key) {
    const r = await fetch("/api/key/check?key=" + encodeURIComponent(key));
    const jr = await r.json();
    if (r.status === 200) {
      Swal.fire({
        title: 'Key details',
        html: `<pre style="text-align:left">${JSON.stringify(jr.result||jr, null, 2)}</pre>`,
        width: 800
      });
    } else {
      Swal.fire("Error", jr.error || JSON.stringify(jr), "error");
    }
  }

  // initial fetch
  fetchKeysAndRender();

  // auto refresh
  setInterval(fetchKeysAndRender, AUTO_REFRESH_MS);

  // search filter live
  searchBox.addEventListener("input", function(){
    // simply refetch rendering (we could cache keys but simpler)
    fetch("/api/keys").then(r=>r.json()).then(j=>renderTable(j.keys || []));
  });
});