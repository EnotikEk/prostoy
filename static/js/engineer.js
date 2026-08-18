// Специфичные функции для инженера

document.addEventListener('DOMContentLoaded', function() {
    // Обновление КПЭ дашборда (AJAX)
    const refreshBtn = document.getElementById('refreshKPI');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            const resetLoading = showLoading(refreshBtn);
            fetch('/api/kpi/refresh')
                .then(response => response.json())
                .then(data => {
                    location.reload();
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Ошибка обновления данных', 'error');
                })
                .finally(() => {
                    resetLoading();
                });
        });
    }
    
    // Массовое утверждение простоев
    const bulkApproveBtn = document.getElementById('bulkApprove');
    if (bulkApproveBtn) {
        bulkApproveBtn.addEventListener('click', function() {
            const checkboxes = document.querySelectorAll('.downtime-checkbox:checked');
            if (checkboxes.length === 0) {
                showToast('Выберите хотя бы один простой', 'warning');
                return;
            }
            
            if (confirm(`Утвердить ${checkboxes.length} простоев?`)) {
                const ids = Array.from(checkboxes).map(cb => cb.value);
                
                fetch('/api/downtimes/bulk-approve', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ids: ids})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showToast('Простои утверждены', 'success');
                        location.reload();
                    } else {
                        showToast(data.message || 'Ошибка', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Ошибка при утверждении', 'error');
                });
            }
        });
    }
    
    // Экспорт реестра
    const exportBtn = document.getElementById('exportRegistry');
    if (exportBtn) {
        exportBtn.addEventListener('click', function() {
            exportTableToCSV('downtimesTable', 'реестр_простоев');
        });
    }
    
    // Фильтры с автообновлением
    const filters = document.querySelectorAll('.auto-filter');
    filters.forEach(filter => {
        filter.addEventListener('change', function() {
            document.getElementById('filterForm').submit();
        });
    });
    
    // Детальный просмотр с AJAX
    const detailButtons = document.querySelectorAll('.view-detail');
    detailButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const downtimeId = btn.getAttribute('data-id');
            fetch(`/api/downtimes/${downtimeId}`)
                .then(response => response.json())
                .then(data => {
                    showDowntimeDetail(data);
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Ошибка загрузки деталей', 'error');
                });
        });
    });
    
    // Поиск по реестру с дебаунсом
    const searchInput = document.getElementById('searchRegistry');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', function() {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                document.getElementById('filterForm').submit();
            }, 500);
        });
    }
});

function showDowntimeDetail(downtime) {
    const modalHtml = `
        <div class="modal fade" id="detailModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Простой #${downtime.id}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p><strong>Судно:</strong> ${downtime.ship_name}</p>
                        <p><strong>Начало:</strong> ${formatDate(downtime.start_time)}</p>
                        <p><strong>Окончание:</strong> ${downtime.end_time ? formatDate(downtime.end_time) : '-'}</p>
                        <p><strong>Длительность:</strong> ${formatDuration(downtime.duration_hours)}</p>
                        <p><strong>Причина:</strong> ${downtime.reason_code} - ${downtime.reason_name}</p>
                        <p><strong>Описание:</strong> ${downtime.description || '-'}</p>
                        <p><strong>Статус:</strong> ${downtime.status}</p>
                        <hr>
                        <h6>Файлы:</h6>
                        ${downtime.files.map(f => `<a href="/uploads/${f.filepath}" target="_blank" class="d-block">${f.filename}</a>`).join('') || 'Нет файлов'}
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('detailModal'));
    modal.show();
    
    document.getElementById('detailModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}