(function () {
  "use strict";

  var form = document.getElementById("context-form");
  var titleNode = document.getElementById("context-title");
  var promptNode = document.getElementById("context-prompt");
  var optionsNode = document.getElementById("context-options");
  var continueButton = document.getElementById("continue-button");
  var cancelButton = document.getElementById("cancel-button");
  var returnButton = document.getElementById("return-button");
  var statusNode = document.getElementById("status");
  var webApp = window.WebApp;
  var selectedOptionId = "";

  function setStatus(message, tone) {
    statusNode.textContent = message;
    statusNode.dataset.tone = tone || "";
  }

  function setBusy(isBusy) {
    optionsNode.disabled = isBusy;
    continueButton.disabled = isBusy || !selectedOptionId;
    cancelButton.disabled = isBusy;
  }

  function initData() {
    if (webApp && typeof webApp.initData === "string") {
      return webApp.initData;
    }
    return "";
  }

  function contextRef(rawInitData) {
    var fromInitData = new URLSearchParams(rawInitData).get("start_param");
    if (fromInitData) {
      return fromInitData;
    }
    return new URLSearchParams(window.location.search).get("context_ref") || "";
  }

  function headers() {
    var rawInitData = initData();
    var launchContext = contextRef(rawInitData);
    if (!rawInitData || !launchContext) {
      return null;
    }
    return {
      "X-KVC-Max-Init-Data": rawInitData,
      "X-KVC-Mini-App-Context": launchContext
    };
  }

  function clearOptions() {
    while (optionsNode.firstChild) {
      optionsNode.removeChild(optionsNode.firstChild);
    }
  }

  function renderOption(option) {
    var optionId = String(option.id || "");
    var row = document.createElement("label");
    var input = document.createElement("input");
    var textWrap = document.createElement("span");
    var labelText = document.createElement("span");

    row.className = "option-row";
    input.type = "radio";
    input.name = "context_option";
    input.value = optionId;
    labelText.className = "option-label";
    labelText.textContent = String(option.label || "");

    textWrap.appendChild(labelText);
    if (option.description) {
      var descriptionText = document.createElement("span");
      descriptionText.className = "option-description";
      descriptionText.textContent = String(option.description);
      textWrap.appendChild(descriptionText);
    }

    input.addEventListener("change", function () {
      selectedOptionId = optionId;
      continueButton.disabled = false;
    });

    row.appendChild(input);
    row.appendChild(textWrap);
    return row;
  }

  function renderInteraction(payload) {
    selectedOptionId = "";
    titleNode.textContent = String(payload.title || "");
    promptNode.textContent = String(payload.prompt || "");
    clearOptions();

    payload.options.forEach(function (option) {
      optionsNode.appendChild(renderOption(option));
    });

    cancelButton.hidden = payload.allow_cancel !== true;
    continueButton.disabled = true;
    setBusy(false);
    setStatus("", "");
  }

  function configureBridge() {
    if (webApp && webApp.BackButton && typeof webApp.BackButton.show === "function") {
      webApp.BackButton.show();
      if (typeof webApp.BackButton.onClick === "function") {
        webApp.BackButton.onClick(function () {
          window.history.back();
        });
      }
    }
    if (webApp && typeof webApp.ready === "function") {
      webApp.ready();
    }
  }

  function loadInteraction() {
    var requestHeaders = headers();
    if (!requestHeaders) {
      setStatus("Откройте выбор снова из чата.", "error");
      setBusy(true);
      return;
    }

    setBusy(true);
    setStatus("Загрузка...", "");
    fetch("/max/app/api/context", {
      method: "GET",
      credentials: "same-origin",
      headers: requestHeaders
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          return { ok: response.ok, payload: payload };
        });
      })
      .then(function (result) {
        if (result.ok && Array.isArray(result.payload.options)) {
          renderInteraction(result.payload);
          return;
        }
        setStatus("Откройте выбор снова из чата.", "error");
      })
      .catch(function () {
        setStatus("Сервис временно недоступен. Попробуйте позже.", "error");
      });
  }

  function finishWithPayload(result, successText) {
    if (result.ok && (result.payload.status === "completed" || result.payload.status === "cancelled")) {
      setStatus(successText, "success");
      setBusy(true);
      return;
    }
    setStatus("Действие не выполнено. Попробуйте открыть выбор снова.", "error");
    setBusy(false);
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var requestHeaders = headers();
    if (!requestHeaders || !selectedOptionId) {
      setStatus("Выберите вариант.", "error");
      return;
    }

    setBusy(true);
    setStatus("Отправляем...", "");
    requestHeaders["Content-Type"] = "application/json";
    fetch("/max/app/api/context", {
      method: "POST",
      credentials: "same-origin",
      headers: requestHeaders,
      body: JSON.stringify({ selected_option_id: selectedOptionId })
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          return { ok: response.ok, payload: payload };
        });
      })
      .then(function (result) {
        finishWithPayload(result, "Выбор отправлен.");
      })
      .catch(function () {
        setStatus("Сервис временно недоступен. Попробуйте позже.", "error");
        setBusy(false);
      });
  });

  cancelButton.addEventListener("click", function () {
    var requestHeaders = headers();
    if (!requestHeaders) {
      setStatus("Откройте выбор снова из чата.", "error");
      return;
    }

    setBusy(true);
    setStatus("Отменяем...", "");
    fetch("/max/app/api/context/cancel", {
      method: "POST",
      credentials: "same-origin",
      headers: requestHeaders
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          return { ok: response.ok, payload: payload };
        });
      })
      .then(function (result) {
        finishWithPayload(result, "Выбор отменен.");
      })
      .catch(function () {
        setStatus("Сервис временно недоступен. Попробуйте позже.", "error");
        setBusy(false);
      });
  });

  returnButton.addEventListener("click", function () {
    window.history.back();
  });

  configureBridge();
  loadInteraction();
})();
