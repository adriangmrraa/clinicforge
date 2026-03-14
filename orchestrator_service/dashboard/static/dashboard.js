// Dashboard JavaScript - Funcionalidades completas

let charts = {};
let currentData = {};

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    // Actualizar precios del modelo seleccionado
    updateModelPrices();
    
    // Inicializar gráficos
    initializeCharts();
    
    // Configurar eventos
    setupEventListeners();
    
    // Mostrar notificación de carga
    showNotification('Dashboard cargado correctamente', 'success');
});

// Actualizar precios del modelo
function updateModelPrices() {
    const modelSelect = document.getElementById('modelSelect');
    if (!modelSelect) return;
    
    const selectedOption = modelSelect.options[modelSelect.selectedIndex];
    const inputPrice = selectedOption.getAttribute('data-input-price');
    const outputPrice = selectedOption.getAttribute('data-output-price');
    
    document.getElementById('inputPrice').textContent = `$${parseFloat(inputPrice).toFixed(6)}`;
    document.getElementById('outputPrice').textContent = `$${parseFloat(outputPrice).toFixed(6)}`;
}

// Inicializar gráficos
function initializeCharts() {
    // Gráfico de costos diarios
    const costCtx = document.getElementById('costChart')?.getContext('2d');
    if (costCtx) {
        charts.costChart = new Chart(costCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Costo Diario (USD)',
                    data: [],
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `$${context.parsed.y.toFixed(4)}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Gráfico de uso por modelo
    const modelCtx = document.getElementById('modelChart')?.getContext('2d');
    if (modelCtx) {
        charts.modelChart = new Chart(modelCtx, {
            type: 'doughnut',
            data: {
                labels: [],
                datasets: [{
                    data: [],
                    backgroundColor: [
                        '#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            boxWidth: 12,
                            font: {
                                size: 11
                            }
                        }
                    }
                }
            }
        });
    }
    
    // Gráfico de uso diario
    const dailyCtx = document.getElementById('dailyUsageChart')?.getContext('2d');
    if (dailyCtx) {
        charts.dailyUsageChart = new Chart(dailyCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Input Tokens',
                        data: [],
                        backgroundColor: '#2563eb',
                        borderWidth: 1
                    },
                    {
                        label: 'Output Tokens',
                        data: [],
                        backgroundColor: '#10b981',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    }
                },
                scales: {
                    x: {
                        stacked: false
                    },
                    y: {
                        stacked: false,
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }
}

// Configurar event listeners
function setupEventListeners() {
    // Actualizar valor de temperatura en tiempo real
    const tempSlider = document.getElementById('temperature');
    if (tempSlider) {
        tempSlider.addEventListener('input', function() {
            document.getElementById('tempValue').textContent = this.value;
        });
    }
    
    // Configurar actualización automática cada 60 segundos
    setInterval(refreshData, 60000);
}

// Refrescar datos
async function refreshData() {
    try {
        showLoading(true);
        
        const response = await axios.get('/dashboard/api/metrics', {
            params: {
                days: 30,
                key: '{{ ceo_access_key }}'
            }
        });
        
        currentData = response.data;
        updateDashboard(currentData);
        showNotification('Datos actualizados correctamente', 'success');
        
    } catch (error) {
        console.error('Error refreshing data:', error);
        showNotification('Error al actualizar datos', 'error');
    } finally {
        showLoading(false);
    }
}

// Actualizar dashboard con nuevos datos
function updateDashboard(data) {
    // Actualizar estadísticas principales
    document.getElementById('totalCost').textContent = `$${data.token_metrics.totals.total_cost_usd.toFixed(2)}`;
    document.getElementById('totalTokens').textContent = data.token_metrics.totals.total_tokens.toLocaleString();
    document.getElementById('totalConvs').textContent = data.token_metrics.totals.total_conversations;
    document.getElementById('efficiencyScore').textContent = `${data.projections.efficiency_score}/100`;
    
    // Actualizar gráfico de costos
    if (charts.costChart && data.daily_usage) {
        const labels = data.daily_usage.map(item => {
            const date = new Date(item.date);
            return date.toLocaleDateString('es-ES', { month: 'short', day: 'numeric' });
        }).reverse();
        
        const costs = data.daily_usage.map(item => item.cost_usd).reverse();
        
        charts.costChart.data.labels = labels;
        charts.costChart.data.datasets[0].data = costs;
        charts.costChart.update();
    }
    
    // Actualizar gráfico de modelos
    if (charts.modelChart && data.model_usage) {
        const labels = data.model_usage.map(item => item.model);
        const tokens = data.model_usage.map(item => item.total_tokens);
        
        charts.modelChart.data.labels = labels;
        charts.modelChart.data.datasets[0].data = tokens;
        charts.modelChart.update();
    }
    
    // Actualizar gráfico de uso diario
    if (charts.dailyUsageChart && data.daily_usage) {
        const labels = data.daily_usage.map(item => {
            const date = new Date(item.date);
            return date.toLocaleDateString('es-ES', { day: 'numeric' });
        }).reverse();
        
        const inputTokens = data.daily_usage.map(item => item.input_tokens).reverse();
        const outputTokens = data.daily_usage.map(item => item.output_tokens).reverse();
        
        charts.dailyUsageChart.data.labels = labels;
        charts.dailyUsageChart.data.datasets[0].data = inputTokens;
        charts.dailyUsageChart.data.datasets[1].data = outputTokens;
        charts.dailyUsageChart.update();
    }
}

// Cambiar modelo
async function updateModel() {
    const modelSelect = document.getElementById('modelSelect');
    const modelId = modelSelect.value;
    
    try {
        showLoading(true);
        
        await axios.post('/dashboard/api/config', {
            OPENAI_MODEL: modelId
        }, {
            headers: {
                'X-CEO-Access-Key': '{{ ceo_access_key }}'
            }
        });
        
        updateModelPrices();
        showNotification(`Modelo actualizado a: ${modelId}`, 'success');
        
        // Refrescar datos para ver cambios
        setTimeout(refreshData, 1000);
        
    } catch (error) {
        console.error('Error updating model:', error);
        showNotification('Error al actualizar modelo', 'error');
    } finally {
        showLoading(false);
    }
}

// Actualizar configuración
async function updateConfig(key, value) {
    try {
        const payload = {};
        payload[key] = value;
        
        await axios.post('/dashboard/api/config', payload, {
            headers: {
                'X-CEO-Access-Key': '{{ ceo_access_key }}'
            }
        });
        
        showNotification(`${key} actualizado correctamente`, 'success');
        
    } catch (error) {
        console.error('Error updating config:', error);
        showNotification(`Error al actualizar ${key}`, 'error');
    }
}

// Cambiar pestañas
function switchTab(tabId) {
    // Remover clase active de todas las pestañas
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    
    // Activar pestaña seleccionada
    document.querySelector(`.tab[onclick="switchTab('${tabId}')"]`).classList.add('active');
    document.getElementById(`tab-${tabId}`).classList.add('active');
}

// Mostrar/ocultar loading
function showLoading(show) {
    const container = document.querySelector('.dashboard-container');
    if (show) {
        container.classList.add('loading');
    } else {
        container.classList.remove('loading');
    }
}

// Mostrar notificación
function showNotification(message, type = 'info') {
    // Crear notificación si no existe
    let notification = document.querySelector('.notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.className = 'notification';
        document.body.appendChild(notification);
    }
    
    // Configurar notificación
    notification.textContent = message;
    notification.className = `notification ${type}`;
    
    // Mostrar
    setTimeout(() => {
        notification.classList.add('show');
    }, 10);
    
    // Ocultar después de 3 segundos
    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

// Exportar configuración
async function exportConfig() {
    try {
        const response = await axios.get('/dashboard/api/config/export', {
            headers: {
                'X-CEO-Access-Key': '{{ ceo_access_key }}'
            }
        });
        
        // Crear blob y descargar
        const blob = new Blob([response.data], { type: 'text/yaml' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `config-${new Date().toISOString().split('T')[0]}.yaml`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
        showNotification('Configuración exportada correctamente', 'success');
        
    } catch (error) {
        console.error('Error exporting config:', error);
        showNotification('Error al exportar configuración', 'error');
    }
}

// Importar configuración
async function importConfig(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    try {
        const reader = new FileReader();
        reader.onload = async function(e) {
            const yamlContent = e.target.result;
            
            const response = await axios.post('/dashboard/api/config/import', {
                yaml: yamlContent
            }, {
                headers: {
                    'X-CEO-Access-Key': '{{ ceo_access_key }}'
                }
            });
            
            if (response.data.success) {
                showNotification('Configuración importada correctamente', 'success');
                setTimeout(refreshData, 1000);
            } else {
                showNotification('Error al importar configuración', 'error');
            }
        };
        
        reader.readAsText(file);
        
    } catch (error) {
        console.error('Error importing config:', error);
        showNotification('Error al importar configuración', 'error');
    }
}

// Inicializar con datos del servidor
window.initialData = {{ {
    'token_metrics': token_metrics,
    'daily_usage': daily_usage,
    'model_usage': model_usage,
    'projections': projections,
    'db_stats': db_stats
} | tojson | safe }};

// Cargar datos iniciales
if (window.initialData) {
    updateDashboard(window.initialData);
}