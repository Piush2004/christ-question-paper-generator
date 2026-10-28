(function () {
  "use strict";
  var meta = JSON.parse(document.getElementById("job-data").textContent);
  var logEl = document.getElementById("job-log");
  var badgeEl = document.getElementById("job-badge");
  var resultEl = document.getElementById("job-result");
  var timer = null;

  function el(tag, props, children) {
    var node = document.createElement(tag);
    Object.keys(props || {}).forEach(function (k) {
      if (k === "class") node.className = props[k];
      else node.setAttribute(k, props[k]);
    });
    (children || []).forEach(function (c) { node.appendChild(c); });
    return node;
  }

  function text(s) { return document.createTextNode(s); }

  function renderBadge(status) {
    if (status === "done") return el("span", { class: "badge badge--ok" }, [text("done")]);
    if (status === "error") return el("span", { class: "badge badge--danger" }, [text("error")]);
    return el("span", { class: "badge badge--warn" }, [
      el("span", { class: "spinner", "aria-hidden": "true" }, []),
      text(" " + status),
    ]);
  }

  function renderResult(result) {
    var panel = el("div", { class: "panel" });
    panel.appendChild(el("div", { class: "panel__head" }, [
      el("strong", {}, [text("Result — version v" + result.version)]),
    ]));
    var body = el("div", { class: "panel__body" });

    var v = result.validation || {};
    body.appendChild(el("p", {}, [
      text("Approvable: "),
      el("span", { class: "badge " + (v.approvable ? "badge--ok" : "badge--danger") }, [
        text(v.approvable ? "yes — all hard checks pass" : "no — see checks below"),
      ]),
    ]));

    if (v.checks && v.checks.length) {
      var table = el("table", { class: "ledger" });
      var thead = el("thead", {}, [el("tr", {}, [el("th", {}, [text("Check")]), el("th", {}, [text("Result")]), el("th", {}, [text("Detail")])])]);
      var tbody = el("tbody");
      v.checks.forEach(function (c) {
        tbody.appendChild(el("tr", {}, [
          el("td", {}, [text(c.name)]),
          el("td", {}, [el("span", { class: "badge " + (c.passed ? "badge--ok" : "badge--danger") }, [text(c.passed ? "pass" : "fail")])]),
          el("td", {}, [text(c.detail || "")]),
        ]));
      });
      table.appendChild(thead);
      table.appendChild(tbody);
      body.appendChild(table);
    }

    if (result.dir && result.files) {
      var links = el("p", {});
      Object.keys(result.files).forEach(function (kind) {
        var a = el("a", { class: "btn btn--ghost", href: "/papers/download/" + result.dir + "/" + result.files[kind], style: "margin-right:8px;" }, [text("Download " + kind.toUpperCase())]);
        links.appendChild(a);
      });
      body.appendChild(links);
    }

    panel.appendChild(body);
    clearChildren(resultEl);
    resultEl.appendChild(panel);
  }

  function renderError(error) {
    var panel = el("div", { class: "panel" });
    var body = el("div", { class: "panel__body" });
    body.appendChild(el("div", { class: "flash flash--error" }, [text(error.type + ": " + error.detail)]));
    if (error.problems && error.problems.length) {
      var list = el("ul");
      error.problems.forEach(function (p) { list.appendChild(el("li", {}, [text(p)])); });
      body.appendChild(list);
    }
    panel.appendChild(body);
    clearChildren(resultEl);
    resultEl.appendChild(panel);
  }

  function clearChildren(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function poll() {
    fetch("/api/jobs/" + meta.jobId)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        logEl.textContent = data.log.join("\n");
        logEl.scrollTop = logEl.scrollHeight;
        clearChildren(badgeEl);
        badgeEl.appendChild(renderBadge(data.status));
        if (data.status === "done") {
          renderResult(data.result);
          clearInterval(timer);
        } else if (data.status === "error") {
          renderError(data.error);
          clearInterval(timer);
        }
      });
  }

  if (meta.status === "done" || meta.status === "error") {
    poll();
  } else {
    poll();
    timer = setInterval(poll, 1500);
  }
})();
