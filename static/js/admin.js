// Специфичные функции для администратора

document.addEventListener('DOMContentLoaded', function() {
    // Редактирование судов прямо в таблице
    const editShipButtons = document.querySelectorAll('.edit-ship');
    editShipButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const shipId = this.getAttribute('data-id');
            const row = document.getElementById(`ship-row-${shipId}`);
            const cells = row.querySelectorAll('.editable');
            
            cells.forEach(cell => {
                const oldValue = cell.innerText;
                const input = document.createElement('input');
                input.value = oldValue;
                input.className = 'form-control form-control-sm';
                cell.innerText = '';
                cell.appendChild(input);
            });
            
            this.style.display = 'none';
            document.getElementById(`save-ship-${shipId}`).style.display = 'inline-block';
        });
    });
    
    // Логирование с фильтрацией
    const logFilters = document.querySelectorAll('.log-filter');
    logFilters.forEach(filter => {
        filter.addEventListener('change', function() {
            loadAuditLogs();
        });
    });
    
    // Ручная корректировка простоя
    const correctDowntimeBtns = document.querySelectorAll('.correct-downtime');
    correctDowntimeBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const downtimeId = this.getAttribute('data-id');
            showCorrectionModal(downtimeId);
        });
    });
    
    // Импорт данных из Excel
    const importBtn = document.getElementById('importExcel');
    if (importBtn) {
        importBtn.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const formData = new FormData();
                formData.append('file', file);
                
                fetch('/admin/import/ships', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showToast(`Импортировано ${data.count} судов`, 'success');
                        location.reload();
                    } else {
                        showToast(data.message || 'Ошибка импорта', 'error');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Ошибка при импорте', 'error');
                });
            }
        });
    }
    
    // Бэкап базы данных
    const backupBtn = document.getElementById('backupDB');
    if (backupBtn) {
        backupBtn.addEventListener('click', function() {
            const resetLoading = showLoading(backupBtn);
            fetch('/admin/backup')
                .then(response => response.blob())
                .then(blob => {
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `backup_${new Date().toISOString().slice(0,19)}.db`;
                    a.click();
                    showToast('Бэкап создан', 'success');
                })
                .catch(error => {
                    console.error('Error:', error);
                    showToast('Ошибка создания бэкапа', 'error');
                })
                .finally(() => {
                    resetLoading();
                });
        });
    }
});

function showCorrectionModal(downtimeId) {
    const modalHtml = `
        <div class="modal fade" id="correctionModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-warning">
                        <h5 class="modal-title">Корректировка простоя #${downtimeId}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <form method="POST" action="/admin/downtime/${downtimeId}/correct">
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label">Новая дата начала</label>
                                <input type="datetime-local" name="start_time" class="form-control" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Новая дата окончания</label>
                                <input type="datetime-local" name="end_time" class="form-control">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Код причины</label>
                                <select name="reason_code" class="form-select">
                                    <option value="">Не менять</option>
                                    <option value="01">01 - Техническая неисправность</option>
                                    <option value="02">02 - Отсутствие ЗИП</option>
                                    <option value="03">03 - Погодные условия</option>
                                    <option value="04">04 - Ожидание грузовых операций</option>
                                    <option value="05">05 - Экипаж</option>
                                    <option value="06">06 - Документальное оформление</option>
                                    <option value="07">07 - Прочие</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Новый статус</label>
                                <select name="status" class="form-select">
                                    <option value="">Не менять</option>
                                    <option value="approved">Утверждён</option>
                                    <option value="rejected">Отклонён</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label">Причина корректировки <span class="text-danger">*</span></label>
                                <textarea name="correction_reason" class="form-control" rows="3" required></textarea>
                                <small class="text-muted">Обязательное поле для аудита</small>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
                            <button type="submit" class="btn btn-warning">Сохранить изменения</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modal = new bootstrap.Modal(document.getElementById('correctionModal'));
    modal.show();
    
    document.getElementById('correctionModal').addEventListener('hidden.bs.modal', function() {
        this.remove();
    });
}

function loadAuditLogs() {
    const userFilter = document.getElementById('log_user')?.value || '';
    const actionFilter = document.getElementById('log_action')?.value || '';
    
    fetch(`/admin/logs?user=${userFilter}&action=${actionFilter}`)
        .then(response => response.json())
        .then(data => {
            const tbody = document.getElementById('logsTableBody');
            if (tbody) {
                tbody.innerHTML = data.logs.map(log => `
                    <tr>
                        <td>${new Date(log.created_at).toLocaleString()}</td>
                        <td>${log.username}</td>
                        <td>${log.action}</td>
                        <td>${log.details || '-'}</td>
                    </tr>
                `).join('');
            }
        })
        .catch(error => console.error('Error:', error));
}