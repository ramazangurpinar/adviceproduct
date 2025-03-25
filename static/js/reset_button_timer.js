document.addEventListener("DOMContentLoaded", function () {
    const form = document.querySelector("form");
    const button = form ? form.querySelector("#resetButton") : null;
  
    if (!form || !button) return;
  
    const existingTime = localStorage.getItem("resetCountdown");
    if (existingTime) {
      const remaining = Math.floor((parseInt(existingTime) - Date.now()) / 1000);
      if (remaining > 0) {
        startCountdown(remaining);
      } else {
        localStorage.removeItem("resetCountdown");
      }
    }
  
    form.addEventListener("submit", function () {
      const seconds = 10;
      const targetTime = Date.now() + seconds * 1000;
      localStorage.setItem("resetCountdown", targetTime);
      startCountdown(seconds);
    });
  
    function startCountdown(seconds) {
      button.disabled = true;
  
      const countdown = setInterval(() => {
        if (seconds > 0) {
          button.value = `Send Reset Link (${seconds})`;
          seconds--;
        } else {
          clearInterval(countdown);
          button.disabled = false;
          button.value = "Send Reset Link";
          localStorage.removeItem("resetCountdown");
        }
      }, 1000);
  
      button.value = `Send Reset Link (${seconds})`;
    }
  });
  