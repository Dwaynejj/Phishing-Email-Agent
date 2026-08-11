chrome.runtime.onInstalled.addListener(() => {
    console.log("PhishShield extension installed");
    chrome.storage.sync.get({ apiBaseUrl: "http://127.0.0.1:5001" }, (stored) => {
        if (!stored.apiBaseUrl) {
            chrome.storage.sync.set({ apiBaseUrl: "http://127.0.0.1:5001" });
        }
    });
});
