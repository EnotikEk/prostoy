// Специфичные функции для капитана

document.addEventListener('DOMContentLoaded', function() {
    // Обработка отправки формы завершения простоя
    const completeForm = document.getElementById('completeForm');
    if (completeForm) {
        completeForm.addEventListener('submit', function(e) {
            const description = document.querySelector('[name="description"]');
            const files = document.querySelector('[name="files"]');
            
            // Проверка длины описания
            if (description && description.value.trim().length < 10) {
                e.preventDefault();
                showToast('Описание должно содержать не менее 10 символов', 'error');
                return false;
            }
            
            // Проверка выбора причины
            const reasonCode = document.querySelector('[name="reason_code"]');
            if (reasonCode && !reasonCode.value) {
                e.preventDefault();
                showToast('Выберите причину простоя', 'error');
                return false;
            }
            
            // Показываем индикатор загрузки
            const submitBtn = completeForm.querySelector('button[type="submit"]');
            const resetLoading = showLoading(submitBtn);
            
            // Реальное ожидание отправки формы
            setTimeout(() => {
                resetLoading();
            }, 3000);
        });
    }
    
    // Предпросмотр загружаемых файлов
    const fileInput = document.querySelector('[name="files"]');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const files = Array.from(e.target.files);
            const previewContainer = document.getElementById('filePreview');
            
            if (!previewContainer) {
                const container = document.createElement('div');
                container.id = 'filePreview';
                container.className = 'mt-3';
                fileInput.parentNode.appendChild(container);
            }
            
            const container = document.getElementById('filePreview');
            container.innerHTML = '';
            
            files.forEach(file => {
                const fileCard = document.createElement('div');
                fileCard.className = 'alert alert-info alert-dismissible fade show';
                fileCard.innerHTML = `
                    <i class="fas fa-file"></i> ${file.name} (${(file.size / 1024).toFixed(1)} KB)
                    <button type="button" class="btn-close" onclick="this.parentElement.remove()"></button>
                `;
                container.appendChild(fileCard);
            });
            
            // Проверка размера файлов
            if (!validateFileSize(files, 10)) {
                e.target.value = '';
                container.innerHTML = '<div class="alert alert-danger">Файлы превышают допустимый размер (10 МБ)</div>';
            }
        });
    }
    
    // Подтверждение отмены простоя
    const cancelButtons = document.querySelectorAll('form[action*="cancel"] button');
    cancelButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('Вы уверены, что хотите отменить этот простой? Все данные будут потеряны.')) {
                e.preventDefault();
            }
        });
    });
    
    // Таймер активного простоя
    const activeDowntimeStart = document.querySelector('[data-active-start]');
    if (activeDowntimeStart) {
        const startTime = activeDowntimeStart.getAttribute('data-active-start');
        updateActiveDowntimeTimer('activeTimer', startTime);
    }
    
    // Фильтрация таблицы истории
    const filterInput = document.getElementById('historyFilter');
    if (filterInput) {
        filterInput.addEventListener('keyup', function() {
            filterTable('historyFilter', 'historyTable');
        });
    }
});

// Быстрый старт простоя
function quickStartDowntime() {
    if (confirm('Начать простой?')) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/captain/downtime/start';
        document.body.appendChild(form);
        form.submit();
    }
}