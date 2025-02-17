// @ts-check

class FileStatus extends HTMLElement {
  connectedCallback() {
    const checkStatus = async () => {
      // UPDATE THESE AS REQUIRED
      const FILE_STATUS_ENDPOINT = "/file-status";
      const CHECK_INTERVAL_MS = 2000;

      const response = await fetch(
        `${FILE_STATUS_ENDPOINT}?id=${this.dataset.id}`
      );
      const responseObj = await response.json();
      this.textContent = responseObj.status;
      this.dataset.status = responseObj.status.toLowerCase();

      // Store the ingest error if the file errored
      if (responseObj.status.toLowerCase() === "error" ||  responseObj.status.toLowerCase() === "connection error. please retry in 5 minutes. if issue persists, file may be too large.") {
        this.dataset.errorMessage = responseObj.ingest_error || "Unknown error occurred";
        updateErrorMessage(); // Call the function when an error occurs
      }

      if (responseObj.status.toLowerCase() === "complete") {
        const evt = new CustomEvent("doc-complete", {
          detail: this,
        });
        document.body.dispatchEvent(evt);
      } else {
        window.setTimeout(checkStatus, CHECK_INTERVAL_MS);
      }
    };

    checkStatus();
  }
}
customElements.define("file-status", FileStatus);

// Error Handling Logic (Add this inside file-status.js)
function updateErrorMessage() {
  const errorDiv = document.querySelector(".rb-docs__upload-error");
  const errorText = errorDiv.querySelector("p[class~='govuk-!-margin-0']");
  let errorMessages = [];

  document.querySelectorAll("file-status[data-status='error']").forEach(fileStatus => {
      let fileName = fileStatus.closest("tr").querySelector(".iai-doc-list__cell--file-name").innerText;
      let errorMessage = fileStatus.dataset.errorMessage.trim();

      if (fileStatus.dataset.status === "connection error. please retry in 5 minutes. if issue persists, file may be too large.") {

        if (errorMessage.includes("RemoteDisconnected")) {
          errorMessages.push(`Error with ${fileName}: File exceeds token limits.`);
        } else {
          errorMessages.push(`Timeout - unable to process ${fileName}: Please contact us on the Teams Support channel with this error message.`);
        }
      }
      else if (fileStatus.dataset.status === "error"){
        if (errorMessage.includes("expected maxLength: 50000")) {
          errorMessages.push(`Error with ${fileName}: File exceeds token limits.`);
        } else if (errorMessage.includes("Increase the value of [bulk_size]")) {
            errorMessages.push(`Error with ${fileName}: File exceeds token limits.`);
        } else if (errorMessage.includes("Too many input tokens. Max input tokens: 8192")) {
            errorMessages.push(`Error with ${fileName}: File exceeds token limits.`);
        } else if (errorMessage.includes("Unstructured failed to extract text")) {
          errorMessages.push(`Error with ${fileName}: Unable to extract content from this file.`);
        } else {
          errorMessages.push(`Other error - unable to process ${fileName}: Please contact us on the Teams Support channel with this error message.`);
        }
      }

  });

  if (errorMessages.length > 0) {
      errorText.innerHTML = errorMessages.join("<br>");
      errorDiv.style.display = "flex";
  } else {
      errorDiv.style.display = "none";
  }
}

// MutationObserver to detect status changes dynamically
document.addEventListener("DOMContentLoaded", function () {
  const observer = new MutationObserver(updateErrorMessage);
  document.querySelectorAll("file-status").forEach(el => {
      observer.observe(el, { attributes: true, attributeFilter: ["data-status", "data-error-message"] });
  });
});