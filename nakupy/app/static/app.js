/* Nakupy - drobna vylepseni; stranka funguje i bez JS. */
(function () {
  "use strict";

  // --- naseptavac nad /api/navrhy ----------------------------------------
  function initSuggest(input) {
    const box = input.closest(".suggest-box");
    const hidden = box.querySelector("input[name=catalog_item_id]");
    let list = null;
    let timer = null;

    function close() {
      if (list) { list.remove(); list = null; }
    }

    function pick(item) {
      input.value = item.name;
      if (hidden) hidden.value = item.id;
      close();
      input.focus();
    }

    function render(items) {
      close();
      if (!items.length) return;
      list = document.createElement("div");
      list.className = "suggest-list";
      items.forEach(function (item) {
        const button = document.createElement("button");
        button.type = "button";
        const hints = [];
        if (item.package) hints.push(item.package);
        if (item.category) hints.push(item.category);
        if (item.deal) {
          hints.push("akce " + item.deal.price.toFixed(2).replace(".", ",") + " Kč" +
            (item.deal.pct ? " (−" + item.deal.pct + " %)" : ""));
        }
        button.innerHTML = '<strong></strong><div class="hint"></div>';
        button.querySelector("strong").textContent = (item.favorite ? "★ " : "") + item.name;
        button.querySelector(".hint").textContent = hints.join(" · ");
        button.addEventListener("click", function () { pick(item); });
        list.appendChild(button);
      });
      box.appendChild(list);
    }

    input.addEventListener("input", function () {
      if (hidden) hidden.value = "";
      clearTimeout(timer);
      const query = input.value.trim();
      if (query.length < 2) { close(); return; }
      timer = setTimeout(function () {
        fetch("/api/navrhy?q=" + encodeURIComponent(query))
          .then(function (r) { return r.ok ? r.json() : { items: [] }; })
          .then(function (data) { render(data.items || []); })
          .catch(close);
      }, 180);
    });

    input.addEventListener("keydown", function (event) {
      if (event.key === "Escape") close();
    });
    document.addEventListener("click", function (event) {
      if (!box.contains(event.target)) close();
    });
  }

  document.querySelectorAll("[data-suggest]").forEach(initSuggest);

  // --- odskrtavani polozek v rezimu nakupu -------------------------------
  function updateProgress(progress) {
    if (!progress) return;
    const bar = document.querySelector("[data-progress-bar]");
    if (bar) bar.style.width = progress.pct + "%";
    document.querySelectorAll("[data-progress-text]").forEach(function (node) {
      node.textContent = progress.done + " / " + progress.total;
    });
    const spent = document.querySelector("[data-spent]");
    if (spent) spent.textContent = progress.spent.toFixed(2).replace(".", ",") + " Kč";
  }

  document.querySelectorAll("form[data-quick-status]").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (!window.fetch) return;
      event.preventDefault();
      const data = new FormData(form);
      form.querySelectorAll("button").forEach(function (b) { b.disabled = true; });
      fetch(form.action, { method: "POST", body: data, headers: { "X-Ajax": "1" } })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
        .then(function (payload) {
          const row = form.closest(".item");
          if (row) {
            row.classList.toggle("done", payload.status === "bought");
            row.classList.toggle("missing", payload.status === "missing");
            const check = row.querySelector(".check");
            if (check) check.classList.toggle("on", payload.status === "bought");
            const price = row.querySelector("[data-item-price]");
            if (price) {
              price.textContent = payload.price
                ? payload.price.toFixed(2).replace(".", ",") + " Kč" : "";
            }
          }
          updateProgress(payload.progress);
        })
        .catch(function () { form.submit(); })
        .finally(function () {
          form.querySelectorAll("button").forEach(function (b) { b.disabled = false; });
        });
    });
  });

  // --- prubezne obnoveni stavu seznamu ----------------------------------
  const watcher = document.querySelector("[data-watch-list]");
  if (watcher && window.fetch) {
    let last = watcher.dataset.updatedAt || "";
    setInterval(function () {
      fetch("/api/seznam/" + watcher.dataset.watchList + "/stav")
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
        .then(function (state) {
          updateProgress(state);
          if (state.updated_at !== last) {
            last = state.updated_at;
            if (watcher.dataset.reload === "1") window.location.reload();
          }
        })
        .catch(function () { /* offline - zkusime priste */ });
    }, 20000);
  }

  // --- stav zpracovani PDF ----------------------------------------------
  const importWatcher = document.querySelector("[data-watch-import]");
  if (importWatcher && window.fetch) {
    const poll = setInterval(function () {
      fetch("/api/import/" + importWatcher.dataset.watchImport + "/stav")
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r); })
        .then(function (state) {
          if (state.status !== "processing") {
            clearInterval(poll);
            window.location.reload();
          }
        })
        .catch(function () { clearInterval(poll); });
    }, 3000);
  }

  // --- potvrzeni destruktivnich akci -------------------------------------
  document.querySelectorAll("[data-confirm]").forEach(function (element) {
    element.addEventListener("submit", function (event) {
      if (!window.confirm(element.dataset.confirm)) event.preventDefault();
    });
  });

  // --- hromadne oznaceni pri importu ------------------------------------
  document.querySelectorAll("[data-toggle-all]").forEach(function (button) {
    button.addEventListener("click", function () {
      const checked = button.dataset.toggleAll === "1";
      document.querySelectorAll("input[name=select]").forEach(function (box) {
        box.checked = checked;
      });
    });
  });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(function () { /* nevadi */ });
  }
})();
