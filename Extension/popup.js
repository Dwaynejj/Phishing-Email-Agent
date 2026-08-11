const DEFAULT_API = "http://127.0.0.1:5001";

document.addEventListener("DOMContentLoaded", () => {
    const resultEl = document.getElementById("result");
    const checkBtn = document.getElementById("checkEmail");
    const apiInput = document.getElementById("apiUrl");

    chrome.storage.sync.get({ apiBaseUrl: DEFAULT_API }, (stored) => {
        if (apiInput) apiInput.value = stored.apiBaseUrl || DEFAULT_API;
    });

    if (document.getElementById("saveApi")) {
        document.getElementById("saveApi").addEventListener("click", () => {
            const value = (apiInput.value || DEFAULT_API).trim().replace(/\/$/, "");
            chrome.storage.sync.set({ apiBaseUrl: value }, () => {
                resultEl.innerHTML = "API URL saved.";
            });
        });
    }

    checkBtn.addEventListener("click", () => {
        resultEl.innerHTML = "Scanning open email…";
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            const tab = tabs[0];
            if (!tab || !tab.id || !tab.url || !tab.url.includes("mail.google.com")) {
                resultEl.innerHTML = "Open a Gmail message first.";
                return;
            }

            chrome.tabs.sendMessage(tab.id, { action: "getEmailContent" }, (response) => {
                if (chrome.runtime.lastError || !response) {
                    // Content script may not be injected yet — inject and retry
                    chrome.scripting.executeScript(
                        { target: { tabId: tab.id }, files: ["content.js"] },
                        () => {
                            chrome.tabs.sendMessage(tab.id, { action: "getEmailContent" }, (retryResponse) => {
                                if (chrome.runtime.lastError || !retryResponse) {
                                    resultEl.innerHTML = "Could not read Gmail content. Refresh the tab and try again.";
                                    return;
                                }
                                handleEmail(retryResponse);
                            });
                        }
                    );
                    return;
                }
                handleEmail(response);
            });
        });
    });

    function handleEmail(email) {
        if (!email.found) {
            resultEl.innerHTML = "No open email found. Open a message in Gmail, then try again.";
            return;
        }
        checkPhishing(email);
    }

    function checkPhishing(email) {
        chrome.storage.sync.get({ apiBaseUrl: DEFAULT_API }, (stored) => {
            const base = (stored.apiBaseUrl || DEFAULT_API).replace(/\/$/, "");
            resultEl.innerHTML = "Contacting PhishShield…";

            fetch(`${base}/detect`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email_text: email.emailText,
                    subject: email.subject || "",
                    sender_domain: email.senderDomain || ""
                })
            })
                .then(async (response) => {
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.error || "Request failed");
                    return data;
                })
                .then((data) => {
                    const label = data.prediction || data.result || "unknown";
                    const confidence = Math.round((data.confidence || 0) * 100);
                    const probability = Math.round((data.probability || 0) * 100);
                    const tone = label === "phishing" ? "#b91c1c" : "#15803d";
                    resultEl.innerHTML =
                        `<strong style="color:${tone}">${label.toUpperCase()}</strong>` +
                        `<br>Confidence: ${confidence}%` +
                        `<br>Phishing probability: ${probability}%` +
                        (email.subject ? `<br><small>Subject: ${escapeHtml(email.subject)}</small>` : "");
                })
                .catch((error) => {
                    resultEl.innerHTML =
                        `Error connecting to backend.<br><small>${escapeHtml(error.message)}. ` +
                        `Start PhishShield with <code>python app.py</code> on port 5001.</small>`;
                });
        });
    }

    function escapeHtml(text) {
        return String(text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }
});
