(function () {
  "use strict";

  var form = document.getElementById("connect-form");
  var apiBaseUrlInput = document.getElementById("api-base-url");
  var tokenInput = document.getElementById("kaiten-token");
  var submitButton = document.getElementById("submit-button");
  var statusNode = document.getElementById("status");
  var returnButton = document.getElementById("return-button");
  var webApp = window.WebApp;

  function setStatus(message, tone) {
    statusNode.textContent = message;
    statusNode.dataset.tone = tone || "";
  }

  function setBusy(isBusy) {
    submitButton.disabled = isBusy;
    apiBaseUrlInput.disabled = isBusy;
    tokenInput.disabled = isBusy;
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

  function clearToken() {
    tokenInput.value = "";
    if (webApp && typeof webApp.disableClosingConfirmation === "function") {
      webApp.disableClosingConfirmation();
    }
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

  tokenInput.addEventListener("input", function () {
    if (!webApp) {
      return;
    }
    if (tokenInput.value && typeof webApp.enableClosingConfirmation === "function") {
      webApp.enableClosingConfirmation();
    }
    if (!tokenInput.value && typeof webApp.disableClosingConfirmation === "function") {
      webApp.disableClosingConfirmation();
    }
  });

  returnButton.addEventListener("click", function () {
    window.history.back();
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var rawInitData = initData();
    var launchContext = contextRef(rawInitData);
    var apiBaseUrl = apiBaseUrlInput.value.trim();
    var token = tokenInput.value;

    if (!rawInitData || !launchContext || !apiBaseUrl || !token) {
      setStatus("Не удалось подтвердить запуск или заполнены не все поля.", "error");
      clearToken();
      return;
    }

    setBusy(true);
    setStatus("Проверяем подключение...", "");

    fetch("/max/app/api/connect", {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        init_data: rawInitData,
        context_ref: launchContext,
        api_base_url: apiBaseUrl,
        token: token
      })
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          return {
            ok: response.ok,
            payload: payload
          };
        });
      })
      .then(function (result) {
        if (result.ok && result.payload.status === "connected") {
          setStatus("Kaiten подключен.", "success");
          returnButton.hidden = false;
          return;
        }
        setStatus("Подключение не выполнено. Проверьте данные и попробуйте снова.", "error");
      })
      .catch(function () {
        setStatus("Сервис временно недоступен. Попробуйте позже.", "error");
      })
      .finally(function () {
        token = "";
        clearToken();
        setBusy(false);
      });
  });

  configureBridge();
})();
