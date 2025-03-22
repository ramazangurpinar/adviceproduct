document.addEventListener("DOMContentLoaded", function () {
    const toggleBtn = document.getElementById("togglePassword");
    const passwordInput = document.getElementById("password");
    const icon = document.getElementById("toggleIcon");
  
    if (toggleBtn && passwordInput && icon) {
      toggleBtn.addEventListener("click", function () {
        const isPassword = passwordInput.getAttribute("type") === "password";
        passwordInput.setAttribute("type", isPassword ? "text" : "password");
  
        // İkonu değiştir
        icon.classList.toggle("bi-eye");
        icon.classList.toggle("bi-eye-slash");
      });
    }
  });
  