console.log("✅ script.js loaded");

// 🧠 Make this global so both submitTasks and onload can access it
const quadrants = [
  'urgent_important',
  'important_not_urgent',
  'not_important_urgent',
  'not_important_not_urgent'  // ✅ FIXED this line
];

let taskCounter = 0;

function addTask() {
  const name = document.getElementById("taskName").value.trim().replace(/,+/g, "").replace(/\s+/g, " ");
  if (!name) {
    alert("Please enter a task name.");
    return;
  }

  const task = document.createElement("div");
  task.className = "task entering";
  task.setAttribute("data-name", name);
  task.id = `task-${Date.now()}`;
  task.innerHTML = `
    ${name}
    <button class="delete-btn" onclick="deleteTask(this)">❌</button>
  `;

  document.getElementById("urgent_important").appendChild(task);
  void task.offsetWidth;
  task.classList.remove("entering");

  document.getElementById("taskName").value = "";
}

function deleteTask(button) {
  const task = button.parentElement;
  task.classList.add("deleting");
  setTimeout(() => task.remove(), 200);
}

function showWorkoutSuggestions() {
  const runCount = document.getElementById("runCount").value;
  const indoorCount = document.getElementById("indoorCount").value;

  fetch(`/generate_workouts?runs=${runCount}&indoor=${indoorCount}`)
    .then(res => res.json())
    .then(data => {
      let out = "<h3>Suggested Workouts:</h3><ul>";
      data.workouts.forEach(w => {
        out += `<li>${w.day}: ${w.type}</li>`;
      });
      out += "</ul>";
      const box = document.getElementById("workoutSuggestions");
      if (box) box.innerHTML = out;
    });
}

function updateMealPreview() {
  const bTime = document.getElementById("breakfastStart").value;
  const bDur = document.getElementById("breakfastDuration").value;
  const lTime = document.getElementById("lunchStart").value;
  const lDur = document.getElementById("lunchDuration").value;
  const mealBox = document.getElementById("mealSummary");

  if (mealBox) {
    mealBox.innerText = `🍳 Breakfast at ${bTime} for ${bDur} min — 🥗 Lunch at ${lTime} for ${lDur} min.`;
  }
}

window.onload = () => {
  // Auto-fill week range
  const today = new Date();
  const dayOfWeek = today.getDay();
  const diffToMonday = today.getDate() - dayOfWeek + (dayOfWeek === 0 ? -6 : 1);
  const monday = new Date(today.setDate(diffToMonday));
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);

  document.getElementById("weekStart").value = monday.toISOString().split('T')[0];
  document.getElementById("weekEnd").value = sunday.toISOString().split('T')[0];

  updateMealPreview();

  // Update meals live
  ["breakfastStart", "breakfastDuration", "lunchStart", "lunchDuration"].forEach(id => {
    document.getElementById(id).addEventListener("input", updateMealPreview);

  });

  // Enable SortableJS
  quadrants.forEach(q => {
    const el = document.getElementById(q);
    if (el) {
      new Sortable(el, {
  group: 'tasks',
  animation: 0,                    // 🔥 No animation at all
  delay: 0,                        // 🔥 No delay before drag starts
  easing: 'linear',
  touchStartThreshold: 0,         // 🔥 Immediate touch drag start
  swapThreshold: 1,               // 🔥 Trigger drop the moment it touches
  dragClass: "drag-active",       // Optional styling for feedback
  fallbackTolerance: 0            // 🔥 Fastest response on fallback
});
    } else {
      console.warn(`⚠️ Sortable skipped: ID "${q}" not found`);
    }
  });

  // Attach listeners
  document.getElementById("submitBtn").addEventListener("click", submitTasks);
  const addBtn = document.getElementById("addTaskBtn");
  if (addBtn) {
    addBtn.addEventListener("click", addTask);
  }
};
function spawnStars(count = 50) {
  const duration = 5000; // 15 seconds
  const spacing = duration / count;

  for (let i = 0; i < count; i++) {
    setTimeout(() => {
      const star = document.createElement("div");
      star.className = "star";
      star.innerText = "⭐";
      star.style.left = `${Math.random() * 100}vw`;
      star.style.fontSize = `${12 + Math.random() * 20}px`;
      star.style.animationDuration = `${6 + Math.random() * 6}s`;
      star.style.animationDelay = "0s";
      document.body.appendChild(star);

      // Clean up star after animation
      setTimeout(() => star.remove(), 12000);
    }, i * spacing);
  }
}


function submitTasks() {
  spawnStars();
  console.log("🧠 submitTasks called");
  const tasks = [];
  const weekStart = document.getElementById("weekStart").value;
  const weekEnd = document.getElementById("weekEnd").value;
  const workStart = document.getElementById("workStart").value;
  const workEnd = document.getElementById("workEnd").value;

  const urgentImportantDays = parseInt(document.getElementById("urgentImportantDays").value);
  const urgentImportantHours = parseFloat(document.getElementById("urgentImportantHours").value);
  const importantNotUrgentDays = parseInt(document.getElementById("importantNotUrgentDays").value);
  const importantNotUrgentHours = parseFloat(document.getElementById("importantNotUrgentHours").value);
  const notImportantUrgentDays = parseInt(document.getElementById("notImportantUrgentDays").value);
  const notImportantUrgentHours = parseFloat(document.getElementById("notImportantUrgentHours").value);
  const notUrgentNotImportantDays = parseInt(document.getElementById("notUrgentNotImportantDays").value);
  const notUrgentNotImportantHours = parseFloat(document.getElementById("notUrgentNotImportantHours").value);

  quadrants.forEach(q => {
    const quadrantEl = document.getElementById(q);
    Array.from(quadrantEl.children).forEach(child => {
      if (child.classList.contains('task')) {
        tasks.push({
          name: child.getAttribute("data-name"),
          quadrant: q
        });
      }
    });
  });

  if (tasks.length === 0) {
    alert("❌ No tasks found in the quadrants!");
    return;
  }

  const payload = {
    tasks,
    weekStart,
    weekEnd,
    urgentImportantDays,
    urgentImportantHours,
    importantNotUrgentDays,
    importantNotUrgentHours,
    notImportantUrgentDays,
    notImportantUrgentHours,
    notUrgentNotImportantDays,
    notUrgentNotImportantHours,
    runCount: parseInt(document.getElementById("runCount").value),
    indoorCount: parseInt(document.getElementById("indoorCount").value),
    breakfastStart: document.getElementById("breakfastStart").value,
    breakfastDuration: parseInt(document.getElementById("breakfastDuration").value),
    lunchStart: document.getElementById("lunchStart").value,
    lunchDuration: parseInt(document.getElementById("lunchDuration").value),
    workStart,
    workEnd
  };

  console.log("▶️ Submitting tasks...");
  console.log("📦 Payload:", JSON.stringify(payload, null, 2));

  fetch('/schedule', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify(payload)
  })
  .then(response => {
    console.log("📥 Response status:", response.status);
    return response.json();
  })
  .then(data => {
    console.log("📥 Response data:", data);
    if (data.status === "success") {
      if (data.warning && data.warning.length > 0) {
        alert(data.warning);
      } else {
        alert("✅ Tasks scheduled successfully!");
      }
    } else {
      alert("❌ Failed to schedule tasks.");
    }
  })
  .catch(error => {
    console.error("❌ Unexpected error:", error);
    alert("❌ Failed to schedule tasks.");
  });

}