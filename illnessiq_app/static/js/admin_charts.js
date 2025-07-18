const pieCtx = document.getElementById('pieChart').getContext('2d');
new Chart(pieCtx, {
  type: 'pie',
  data: {
    labels: pieLabels,
    datasets: [{
      label: 'Prediction Distribution',
      data: pieData,
      backgroundColor: [
        'rgba(54, 162, 235, 0.6)',
        'rgba(255, 99, 132, 0.6)',
        'rgba(255, 206, 86, 0.6)',
        'rgba(75, 192, 192, 0.6)'
      ],
      borderColor: [
        'rgba(54, 162, 235, 1)',
        'rgba(255, 99, 132, 1)',
        'rgba(255, 206, 86, 1)',
        'rgba(75, 192, 192, 1)'
      ],
      borderWidth: 1
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom'
      }
    }
  }
});


const chartColors = {
  'thyroid': 'rgba(54, 162, 235, 1)',
  'diabetes': 'rgba(255, 99, 132, 1)',
  'heart': 'rgba(255, 206, 86, 1)',
  'liver': 'rgba(75, 192, 192, 1)'
};

Object.keys(diseaseTrendData).forEach(disease => {
  const slug = disease.toLowerCase();
  const canvasId = `lineChart_${slug}`;
  const canvas = document.getElementById(canvasId);

  if (!canvas) {
    console.warn(`Canvas element not found for disease: ${disease} (ID: ${canvasId})`);
    return;
  }

  const ctx = canvas.getContext('2d');
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: dateLabels,
      datasets: [{
        label: `${disease} Predictions`,
        data: diseaseTrendData[disease],
        borderColor: chartColors[slug] || 'rgba(0,0,0,1)',
        backgroundColor: (chartColors[slug] || 'rgba(0,0,0,1)').replace('1)', '0.2)'),
        fill: true,
        tension: 0.4,
        borderWidth: 2,
        pointHoverRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
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
});
