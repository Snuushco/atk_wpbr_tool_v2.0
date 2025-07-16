// Utility functies
function showAlert(message, type = 'success') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    const main = document.querySelector('main');
    main.insertBefore(alertDiv, main.firstChild);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

// Form validatie
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

function validatePassword(password) {
    return password.length >= 8;
}

// Client-side file storage voor upload beveiliging
class ClientFileStorage {
    constructor() {
        this.files = new Map();
        this.maxFileSize = 16 * 1024 * 1024; // 16MB
        this.allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'application/pdf'];
    }

    // Voeg bestand toe aan client storage
    addFile(fileKey, file) {
        if (file.size > this.maxFileSize) {
            throw new Error(`Bestand is te groot. Maximum grootte: ${this.maxFileSize / 1024 / 1024}MB`);
        }
        
        if (!this.allowedTypes.includes(file.type)) {
            throw new Error('Ongeldig bestandstype. Toegestane types: JPG, PNG, PDF');
        }

        this.files.set(fileKey, file);
        this.updateFilePreview(fileKey, file);
        this.saveToSessionStorage();
    }

    // Verwijder bestand uit client storage
    removeFile(fileKey) {
        this.files.delete(fileKey);
        this.removeFilePreview(fileKey);
        this.saveToSessionStorage();
    }

    // Haal bestand op uit client storage
    getFile(fileKey) {
        return this.files.get(fileKey);
    }

    // Haal alle bestanden op
    getAllFiles() {
        return Array.from(this.files.entries());
    }

    // Update file preview in de UI
    updateFilePreview(fileKey, file) {
        const fileInput = document.getElementById(fileKey);
        if (!fileInput) return;

        // Maak preview container als deze nog niet bestaat
        let previewContainer = fileInput.parentNode.querySelector('.file-preview');
        if (!previewContainer) {
            previewContainer = document.createElement('div');
            previewContainer.className = 'file-preview';
            previewContainer.style.marginTop = '10px';
            fileInput.parentNode.appendChild(previewContainer);
        }

        // Toon bestandsinfo
        previewContainer.innerHTML = `
            <div class="file-item" style="display: flex; align-items: center; gap: 10px; padding: 8px; background: #f8f9fa; border-radius: 4px; margin-bottom: 5px;">
                <span class="file-name" style="flex: 1;">${file.name}</span>
                <span class="file-size" style="color: #666;">${(file.size / 1024).toFixed(1)} KB</span>
                <button type="button" class="remove-file-btn" style="background: #dc3545; color: white; border: none; padding: 2px 6px; border-radius: 3px; cursor: pointer;" onclick="clientFileStorage.removeFile('${fileKey}')">×</button>
            </div>
        `;
    }

    // Verwijder file preview uit de UI
    removeFilePreview(fileKey) {
        const fileInput = document.getElementById(fileKey);
        if (!fileInput) return;

        const previewContainer = fileInput.parentNode.querySelector('.file-preview');
        if (previewContainer) {
            previewContainer.remove();
        }
        
        // Reset file input
        fileInput.value = '';
    }

    // Sla bestanden op in sessionStorage (voor page refresh)
    saveToSessionStorage() {
        const fileData = {};
        this.files.forEach((file, key) => {
            fileData[key] = {
                name: file.name,
                size: file.size,
                type: file.type,
                lastModified: file.lastModified
            };
        });
        sessionStorage.setItem('clientFiles', JSON.stringify(fileData));
    }

    // Laad bestanden uit sessionStorage
    loadFromSessionStorage() {
        const fileData = sessionStorage.getItem('clientFiles');
        if (fileData) {
            try {
                const data = JSON.parse(fileData);
                // We kunnen de bestanden zelf niet herstellen, maar wel de metadata tonen
                Object.keys(data).forEach(key => {
                    const fileInfo = data[key];
                    this.showFileInfo(key, fileInfo);
                });
            } catch (e) {
                console.error('Error loading file data from sessionStorage:', e);
            }
        }
    }

    // Toon bestandsinfo zonder het bestand zelf
    showFileInfo(fileKey, fileInfo) {
        const fileInput = document.getElementById(fileKey);
        if (!fileInput) return;

        let previewContainer = fileInput.parentNode.querySelector('.file-preview');
        if (!previewContainer) {
            previewContainer = document.createElement('div');
            previewContainer.className = 'file-preview';
            previewContainer.style.marginTop = '10px';
            fileInput.parentNode.appendChild(previewContainer);
        }

        previewContainer.innerHTML = `
            <div class="file-item" style="display: flex; align-items: center; gap: 10px; padding: 8px; background: #f8f9fa; border-radius: 4px; margin-bottom: 5px;">
                <span class="file-name" style="flex: 1;">${fileInfo.name} (herlaad vereist)</span>
                <span class="file-size" style="color: #666;">${(fileInfo.size / 1024).toFixed(1)} KB</span>
                <span style="color: #dc3545; font-size: 12px;">Bestand verloren bij page refresh</span>
            </div>
        `;
    }

    // Maak FormData object met alle bestanden voor verzending
    createFormData(formData) {
        const finalFormData = new FormData();
        
        // Voeg alle form data toe
        for (let [key, value] of formData.entries()) {
            finalFormData.append(key, value);
        }

        // Voeg alle bestanden toe
        this.files.forEach((file, key) => {
            finalFormData.append(key, file);
        });

        return finalFormData;
    }

    // Clear alle bestanden
    clear() {
        this.files.clear();
        sessionStorage.removeItem('clientFiles');
        
        // Verwijder alle previews
        document.querySelectorAll('.file-preview').forEach(container => {
            container.remove();
        });
    }
}

// Global instance van client file storage
const clientFileStorage = new ClientFileStorage();

// File upload preview met client-side storage
function setupFileUpload() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(fileInput => {
        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            const fileKey = fileInput.id;
            
            if (files.length === 0) return;

            try {
                // Voor id_file: meerdere bestanden toestaan
                if (fileKey === 'id_file') {
                    if (files.length > 2) {
                        alert('Je mag maximaal 2 bestanden uploaden voor het identiteitsbewijs (voor- en achterzijde).');
                        fileInput.value = '';
                        return;
                    }
                    
                    // Verwijder oude bestanden voor deze key
                    clientFileStorage.removeFile(fileKey);
                    
                    // Voeg nieuwe bestanden toe
                    files.forEach((file, index) => {
                        const fileKeyWithIndex = `${fileKey}_${index}`;
                        clientFileStorage.addFile(fileKeyWithIndex, file);
                    });
                } else {
                    // Voor andere bestanden: alleen het eerste bestand
                    const file = files[0];
                    clientFileStorage.addFile(fileKey, file);
                }
            } catch (error) {
                alert(error.message);
                fileInput.value = '';
            }
        });
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupFileUpload();
    clientFileStorage.loadFromSessionStorage();
    
    // Bijlage-checkboxen koppelen aan file inputs
    const bijlagen = [
        'pasfoto', 'handtekening', 'svpb', 'horeca', 'voetbal', 'logo',
        'straf_belgie', 'fuhrung', 'straf_herkomst', 'pv'
    ];
    
    // Speciaal voor id: één uploader, max 2 files, verplicht als aangevinkt
    const idCheckbox = document.getElementById('id');
    const idFile = document.getElementById('id_file');
    const idFileHint = document.getElementById('id_file_hint');
    if (idCheckbox && idFile) {
        idFile.style.display = idCheckbox.checked ? 'block' : 'none';
        if (idFileHint) idFileHint.style.display = idCheckbox.checked ? 'block' : 'none';
        idCheckbox.addEventListener('change', function() {
            idFile.style.display = this.checked ? 'block' : 'none';
            if (idFileHint) idFileHint.style.display = this.checked ? 'block' : 'none';
            if (!this.checked) {
                idFile.value = '';
                // Verwijder ook uit client storage
                clientFileStorage.removeFile('id_file_0');
                clientFileStorage.removeFile('id_file_1');
            }
        });
    }
    
    // Overige bijlagen: verplicht als aangevinkt, anders niet
    bijlagen.forEach(function(bijlage) {
        const checkbox = document.getElementById(bijlage);
        const fileInput = document.getElementById(bijlage + '_file');
        if (!checkbox || !fileInput) return;
        fileInput.style.display = checkbox.checked ? 'block' : 'none';
        checkbox.addEventListener('change', function() {
            fileInput.style.display = this.checked ? 'block' : 'none';
            if (!this.checked) {
                fileInput.value = '';
                // Verwijder ook uit client storage
                clientFileStorage.removeFile(bijlage + '_file');
            }
        });
    });
});

// Aangepaste form submission voor client-side file storage
function setupFormSubmission() {
    const form = document.getElementById('aanvraagForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Maak FormData met client-side bestanden
        const formData = new FormData(form);
        const finalFormData = clientFileStorage.createFormData(formData);
        
        try {
            const response = await fetch(form.action, {
                method: 'POST',
                body: finalFormData
            });
            
            if (response.redirected) {
                window.location.href = response.url;
            } else {
                const data = await response.json();
                if (data.success) {
                    showAlert(data.message);
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    }
                } else {
                    showAlert(data.message || 'Er is een fout opgetreden', 'error');
                }
            }
        } catch (error) {
            console.error('Error:', error);
            showAlert('Er is een fout opgetreden bij het verzenden', 'error');
        }
    });
}

// Registratie form handler
document.addEventListener('DOMContentLoaded', () => {
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const errorDiv = document.getElementById('registerError');
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
            
            const name = document.getElementById('name').value.trim();
            if (!name) {
                errorDiv.textContent = 'Vul een bedrijfsnaam in.';
                errorDiv.style.display = 'block';
                return;
            }
            const password = document.getElementById('password').value;
            const confirmPassword = document.getElementById('confirm_password').value;
            const vergunningnummer = document.getElementById('vergunningnummer').value;
            const vergunningnummerPattern = /^(ND|BD|HBD|HND|PAC|PGW|POB|VTC)[0-9]{4,}$/i;
            if (!vergunningnummerPattern.test(vergunningnummer)) {
                errorDiv.textContent = 'Vul een geldig vergunningnummer in (bijv. ND6250).';
                errorDiv.style.display = 'block';
                return;
            }
            if (password !== confirmPassword) {
                errorDiv.textContent = 'Wachtwoorden komen niet overeen';
                errorDiv.style.display = 'block';
                return;
            }
            const formData = {
                name: name,
                email: document.getElementById('email').value,
                password: password,
                vergunningnummer: vergunningnummer
            };
            try {
                const response = await fetch('/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(formData)
                });
                const data = await response.json();
                if (data.success) {
                    window.location.href = document.getElementById('loginUrl').value;
                } else {
                    errorDiv.textContent = data.message || 'Registratie mislukt';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                console.error('Error:', error);
                errorDiv.textContent = 'Er is een fout opgetreden bij het registreren';
                errorDiv.style.display = 'block';
            }
        });
    }
});

// Automatische nul-aanvulling vergunningnummer
const vergunningnummerInput = document.getElementById('vergunningnummer');
if (vergunningnummerInput) {
    vergunningnummerInput.addEventListener('blur', function() {
        let val = vergunningnummerInput.value.trim().toUpperCase();
        const match = val.match(/^([A-Z]{2,4})([0-9]{1,5})$/);
        if (match) {
            const type = match[1];
            let nummer = match[2].padStart(5, '0');
            vergunningnummerInput.value = type + nummer;
        }
    });
}

// Cleanup bij page unload
window.addEventListener('beforeunload', function(e) {
    // Alleen cleanup als er bestanden zijn
    if (clientFileStorage.getAllFiles().length > 0) {
        e.preventDefault();
        e.returnValue = '';
        
        // Maak cleanup call naar server
        fetch('/cleanup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        }).catch(() => {
            // Ignore errors bij page unload
        });
    }
});

// Setup form submission als de pagina geladen is
document.addEventListener('DOMContentLoaded', setupFormSubmission); 