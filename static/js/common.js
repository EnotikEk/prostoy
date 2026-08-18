// Общие функции для всего приложения

// Автоматическое скрытие уведомлений через 5 секунд
document.addEventListener('DOMContentLoaded', function() {
    // Авто-скрытие alert
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            setTimeout(function() {
                bsAlert.close();
            }, 5000);
        });
    }, 1000);
    
    // Подтверждение опасных действий
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            if (!confirm(btn.getAttribute('data-confirm'))) {
                e.preventDefault();
                return false;
            }
        });
    });
    
    // Валидация форм на клиенте
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });
});

// Функция для отображения загрузки
function showLoading(button) {
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
    return function() {
        button.disabled = false;
        button.innerHTML = originalText;
    };
}

// Функция для форматирования даты
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Функция для форматирования длительности
function formatDuration(hours) {
    if (hours < 1) {
        return Math.round(hours * 60) + ' мин';
    } else if (hours < 24) {
        return hours.toFixed(1) + ' ч';
    } else {
        const days = Math.floor(hours / 24);
        const remainingHours = hours % 24;
        return days + ' д ' + remainingHours.toFixed(1) + ' ч';
    }
}

// Поиск и фильтрация таблиц
function filterTable(inputId, tableId) {
    const input = document.getElementById(inputId);
    const filter = input.value.toUpperCase();
    const table = document.getElementById(tableId);
    const tr = table.getElementsByTagName('tr');
    
    for (let i = 1; i < tr.length; i++) {
        let txtValue = tr[i].textContent || tr[i].innerText;
        if (txtValue.toUpperCase().indexOf(filter) > -1) {
            tr[i].style.display = '';
        } else {
            tr[i].style.display = 'none';
        }
    }
}

// Экспорт таблицы в CSV
function exportTableToCSV(tableId, filename) {
    const table = document.getElementById(tableId);
    let csv = [];
    
    for (let i = 0; i < table.rows.length; i++) {
        const row = table.rows[i];
        const rowData = [];
        
        for (let j = 0; j < row.cells.length; j++) {
            let cellData = row.cells[j].innerText;
            cellData = cellData.replace(/,/g, ';');
            rowData.push(cellData);
        }
        
        csv.push(rowData.join(','));
    }
    
    const csvFile = new Blob([csv.join('\n')], {type: 'text/csv'});
    const downloadLink = document.createElement('a');
    downloadLink.download = filename + '.csv';
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.click();
}

// Проверка размера файлов
function validateFileSize(files, maxSizeMB = 5) {
    const maxSize = maxSizeMB * 1024 * 1024;
    for (let i = 0; i < files.length; i++) {
        if (files[i].size > maxSize) {
            alert(`Файл ${files[i].name} превышает ${maxSizeMB} МБ`);
            return false;
        }
    }
    return true;
}

// Автосохранение черновика
let autoSaveTimeout;
function autoSaveDraft(formId, callback) {
    clearTimeout(autoSaveTimeout);
    autoSaveTimeout = setTimeout(function() {
        const formData = new FormData(document.getElementById(formId));
        callback(formData);
    }, 3000);
}

// Обновление времени активного простоя
function updateActiveDowntimeTimer(elementId, startTime) {
    const start = new Date(startTime);
    const timerElement = document.getElementById(elementId);
    
    if (!timerElement) return;
    
    function update() {
        const now = new Date();
        const diff = Math.floor((now - start) / 1000);
        const hours = Math.floor(diff / 3600);
        const minutes = Math.floor((diff % 3600) / 60);
        const seconds = diff % 60;
        
        timerElement.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    
    update();
    setInterval(update, 1000);
}

// Обработка ошибок AJAX
function handleAjaxError(xhr, status, error) {
    console.error('AJAX Error:', error);
    let message = 'Произошла ошибка при выполнении запроса';
    
    if (xhr.responseJSON && xhr.responseJSON.message) {
        message = xhr.responseJSON.message;
    } else if (xhr.status === 403) {
        message = 'Доступ запрещён';
    } else if (xhr.status === 404) {
        message = 'Ресурс не найден';
    }
    
    showToast(message, 'error');
}

// Глобальное хранилище интервалов
window.activeIntervals = window.activeIntervals || [];

// Функция для безопасного добавления интервала
function setSafeInterval(callback, delay) {
    var intervalId = setInterval(callback, delay);
    window.activeIntervals.push(intervalId);
    return intervalId;
}

// Функция для очистки всех интервалов
function clearAllIntervals() {
    for (var i = 0; i < window.activeIntervals.length; i++) {
        clearInterval(window.activeIntervals[i]);
    }
    window.activeIntervals = [];
}

// Очистка интервалов при выгрузке страницы
window.addEventListener('beforeunload', function() {
    clearAllIntervals();
});

// Показать всплывающее уведомление
function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.style.position = 'fixed';
        container.style.bottom = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    
    const toastId = 'toast-' + Date.now();
    const bgClass = type === 'error' ? 'bg-danger' : (type === 'success' ? 'bg-success' : 'bg-info');
    
    const toastHtml = `
        <div id="${toastId}" class="toast align-items-center text-white ${bgClass} border-0 mb-2" role="alert">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    document.getElementById('toast-container').insertAdjacentHTML('beforeend', toastHtml);
    const toastElement = document.getElementById(toastId);
    const toast = new bootstrap.Toast(toastElement, {delay: 5000});
    toast.show();
    
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}