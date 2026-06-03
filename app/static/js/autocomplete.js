// Ticker autocomplete: query /api/tickers/search, fill #ticker + #name on pick.
(function () {
  var input = document.getElementById("ticker-search");
  var results = document.getElementById("ticker-results");
  var tickerField = document.getElementById("ticker");
  var nameField = document.getElementById("name");
  if (!input || !results) return;

  var timer = null;

  function clearResults() {
    results.innerHTML = "";
    results.classList.remove("open");
  }

  function render(items) {
    results.innerHTML = "";
    if (!items.length) {
      clearResults();
      return;
    }
    items.forEach(function (it) {
      var li = document.createElement("li");
      li.textContent = it.label;
      li.addEventListener("mousedown", function (e) {
        e.preventDefault(); // keep focus / avoid blur race
        if (tickerField) tickerField.value = it.ticker;
        if (nameField) nameField.value = it.name;
        input.value = it.label;
        clearResults();
      });
      results.appendChild(li);
    });
    results.classList.add("open");
  }

  function query(q) {
    fetch("/api/tickers/search?q=" + encodeURIComponent(q))
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(clearResults);
  }

  input.addEventListener("input", function () {
    var q = input.value.trim();
    if (timer) clearTimeout(timer);
    if (q.length < 1) {
      clearResults();
      return;
    }
    timer = setTimeout(function () { query(q); }, 180);
  });

  document.addEventListener("click", function (e) {
    if (e.target !== input) clearResults();
  });
})();
