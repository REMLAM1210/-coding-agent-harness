const taskInput = document.getElementById("task");
const submitBtn = document.getElementById("submit-btn");
const eventsDiv = document.getElementById("events");
const hitlSection = document.getElementById("hitl");
const hitlAction = document.getElementById("hitl-action");

function addEvent(text, cls = "") {
    const div = document.createElement("div");
    div.className = "event " + cls;
    div.textContent = text;
    eventsDiv.appendChild(div);
    eventsDiv.scrollTop = eventsDiv.scrollHeight;
}

submitBtn.addEventListener("click", async () => {
    const task = taskInput.value.trim();
    if (!task) return;
    eventsDiv.innerHTML = "";
    const resp = await fetch("/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task }),
    });
    const data = await resp.json();
    if (resp.ok) {
        addEvent(`Session created: ${data.session_id}`, "event-success");
        connectWebSocket(data.session_id);
    } else {
        addEvent(`Error: ${data.detail}`, "event-error");
    }
});

function connectWebSocket(sid) {
    const ws = new WebSocket(`ws://${location.host}/sessions/${sid}/stream`);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        addEvent(JSON.stringify(data), data.event_type === "FeedbackSignalEmitted" ? "event-feedback" : "");
        if (data.event_type === "HitlApprovalRequired") {
            hitlSection.hidden = false;
            hitlAction.textContent = JSON.stringify(data.action);
        }
        if (data.event_type === "LoopFinished") {
            addEvent(`Loop finished: ${data.reason}`, "event-success");
        }
    };
    ws.onclose = () => addEvent("WebSocket closed", "");
}

document.getElementById("approve-btn").addEventListener("click", () => approveSession(true));
document.getElementById("deny-btn").addEventListener("click", () => approveSession(false));

async function approveSession(approve) {
    // session_id would be stored from creation
    hitlSection.hidden = true;
}
