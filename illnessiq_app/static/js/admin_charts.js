const pieCtx = document.getElementById('pieChart').getContext('2d');
new Chart(pieCtx, {
  type: 'pie',
  data: {
    labels: pieLabels,
    datasets: [{
      label: 'Prediction Distribution',
      data: pieData,
      borderWidth: 1
    }]
  },
  options: {
    responsive: true,
    plugins: {
      legend: {
        position: 'bottom'
      }
    }
  }
});

const chartColors = {
  'Thyroid': 'rgba(54, 162, 235, 1)',
  'Diabetes': 'rgba(255, 99, 132, 1)',
  'Heart': 'rgba(255, 206, 86, 1)',
  'Liver': 'rgba(75, 192, 192, 1)'
};

const lineCtx = document.getElementById('lineChart').getContext('2d');
new Chart(lineCtx, {
  type: 'line',
  data: {
    labels: lineLabels,
    datasets: Object.keys(lineData).map(disease => ({
      label: disease,
      data: lineData[disease],
      borderColor: chartColors[disease],
      backgroundColor: chartColors[disease].replace('1)', '0.2)'),
      fill: true,
      tension: 0.4,
      borderWidth: 2
    }))
  },
  options: {
    responsive: true,
    plugins: {
      legend: {
        position: 'bottom'
      }
    },
    scales: {
      y: {
        beginAtZero: true,
        precision: 0
      }
    }
  }
});
