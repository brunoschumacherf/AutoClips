const canvas = document.getElementById("analytics-chart");
const rawData = document.getElementById("analytics-chart-data");

if (canvas && rawData && window.Chart) {
  const points = JSON.parse(rawData.textContent);
  new window.Chart(canvas, {
    type: "bar",
    data: {
      labels: points.map(({ day }) => day),
      datasets: [
        {
          label: "Vídeos concluídos",
          data: points.map(({ total }) => total),
          backgroundColor: "#c3fe79",
          borderRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#a6a9be" } } },
      scales: {
        x: { ticks: { color: "#a6a9be" }, grid: { color: "#262837" } },
        y: {
          beginAtZero: true,
          ticks: { color: "#a6a9be", precision: 0 },
          grid: { color: "#262837" },
        },
      },
    },
  });
}
