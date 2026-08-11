function getOpenEmail() {
    const bodyEl =
        document.querySelector(".a3s.aiL") ||
        document.querySelector(".a3s") ||
        document.querySelector("[data-message-id] .a3s");

    const subjectEl =
        document.querySelector("h2.hP") ||
        document.querySelector("[data-thread-perm-id] h2") ||
        document.querySelector(".ha h2");

    const fromEl =
        document.querySelector("span.gD") ||
        document.querySelector("[email].gD") ||
        document.querySelector(".gD");

    const emailText = bodyEl ? (bodyEl.innerText || bodyEl.textContent || "").trim() : "";
    const subject = subjectEl ? (subjectEl.innerText || subjectEl.textContent || "").trim() : "";
    const from = fromEl
        ? (fromEl.getAttribute("email") || fromEl.getAttribute("data-hovercard-id") || fromEl.innerText || "").trim()
        : "";

    let senderDomain = "";
    const domainMatch = from.match(/@([\w.-]+\.\w{2,})/);
    if (domainMatch) {
        senderDomain = domainMatch[1].toLowerCase();
    }

    return {
        emailText,
        subject,
        from,
        senderDomain,
        found: Boolean(emailText || subject)
    };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === "getEmailContent") {
        sendResponse(getOpenEmail());
        return true;
    }
    return false;
});
