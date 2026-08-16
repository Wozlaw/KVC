(function () {
  "use strict";

  var form = document.getElementById("notifications-form");
  var enabledInput = document.getElementById("enabled");
  var dueSoonDaysInput = document.getElementById("due-soon-days");
  var timezoneInput = document.getElementById("timezone");
  var saveButton = document.getElementById("save-button");
  var statusNode = document.getElementById("status");
  var returnButton = document.getElementById("return-button");
  var webApp = window.WebApp;

  function setStatus(message, tone) {
    statusNode.textContent = message;
    statusNode.dataset.tone = tone || "";
  }

  function setBusy(isBusy) {
    saveButton.disabled = isBusy;
    enabledInput.disabled = isBusy;
    dueSoonDaysInput.disabled = isBusy;
    timezoneInput.disabled = isBusy;
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

  function applySettings(settings) {
    enabledInput.checked = settings.enabled === true;
    dueSoonDaysInput.value = String(settings.due_soon_days);
    timezoneInput.value = settings.timezone;
  }

  function currentSettings() {
    var days = Number(dueSoonDaysInput.value);
    if (!Number.isInteger(days) || days < 0 || days > 30) {
      throw new Error("invalid days");
    }
    var timezone = timezoneInput.value.trim();
    if (!timezone) {
      throw new Error("invalid timezone");
    }
    return {
      enabled: enabledInput.checked,
      due_soon_days: days,
      timezone: timezone
    };
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

  function loadSettings() {
    var requestHeaders = headers();
    if (!requestHeaders) {
      setStatus("Откройте настройки снова из чата.", "error");
      setBusy(true);
      return;
    }

    setBusy(true);
    setStatus("Загрузка...", "");
    fetch("/max/app/api/notifications", {
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
        if (result.ok) {
          applySettings(result.payload);
          setStatus("", "");
          setBusy(false);
          return;
        }
        setStatus("Откройте настройки снова из чата.", "error");
      })
      .catch(function () {
        setStatus("Сервис временно недоступен. Попробуйте позже.", "error");
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    var requestHeaders = headers();
    if (!requestHeaders) {
      setStatus("Откройте настройки снова из чата.", "error");
      return;
    }

    var settings;
    try {
      settings = currentSettings();
    } catch (error) {
      setStatus("Проверьте дни и часовой пояс.", "error");
      return;
    }

    setBusy(true);
    setStatus("Сохраняем...", "");
    requestHeaders["Content-Type"] = "application/json";

    fetch("/max/app/api/notifications", {
      method: "POST",
      credentials: "same-origin",
      headers: requestHeaders,
      body: JSON.stringify(settings)
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          return { ok: response.ok, payload: payload };
        });
      })
      .then(function (result) {
        if (result.ok && result.payload.status === "saved") {
          applySettings(result.payload.settings);
          setStatus("Настройки сохранены.", "success");
          return;
        }
        setStatus("Настройки не сохранены. Проверьте поля.", "error");
      })
      .catch(function () {
        setStatus("Сервис временно недоступен. Попробуйте позже.", "error");
      })
      .finally(function () {
        setBusy(false);
      });
  });

  returnButton.addEventListener("click", function () {
    window.history.back();
  });

  configureBridge();
  loadSettings();
})();
