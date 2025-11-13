frappe.ui.form.on("Insurance Policy", {

    // 🔹 Obliczanie prowizji
    calculate_your_commission(frm) {
        calculateCommission(frm);
    },

    insurance_components_add(frm) {
        calculateCommission(frm);
    },

    insurance_components_remove(frm) {
        calculateCommission(frm);
    },



    // 🔹 Gdy użytkownik doda nowy plik PDF
    policy_fille(frm) {
        if (!frm.doc.policy_fille || !frm.doc.policy_fille.endsWith(".pdf")) {
            frappe.msgprint(__("📄 Dodaj plik PDF, aby uruchomić OCR."));
            return;
        }

        frappe.show_alert({
            message: frm.doc.__islocal
                ? __("📄 Analiza OCR (tryb tymczasowy)...")
                : __("📄 OCR uruchomiony dla zapisanego dokumentu..."),
            indicator: "blue"
        });

        // 🔸 Wywołanie OCR
        frappe.call({
            method: "agencik.policy.doctype.insurance_policy.policy_ocr.process_policy_temp",
            args: { data: JSON.stringify(frm.doc) },
            freeze: true,
            freeze_message: __("⏳ Trwa analiza dokumentu PDF przez OCR..."),
            callback: function (r) {
                console.log("📘 OCR response:", r);
                if (r.message && r.message.success && r.message.data) {
                    const data = r.message.data;
                    console.log("📘 OCR extracted data:", data);
                    fillFormWithOcrData(frm, data);
                    frappe.show_alert({
                        message: __("✅ Dane z OCR zostały uzupełnione. Zapisz dokument, jeśli wszystko się zgadza."),
                        indicator: "green"
                    });
                } else {
                    console.error("❌ OCR Error:", r);
                    frappe.msgprint(__("❌ Nie udało się przetworzyć dokumentu OCR."));
                }
            }
        });
    },


    // 🔹 Ustawienie daty końca ochrony
    onload(frm) {
        if (frm.doc.coverage_start && !frm.doc.coverage_end) {
            setCoverageEnd(frm);
        }
    },

    coverage_start(frm) {
        console.log("📅 coverage_start changed to:", frm.doc.coverage_start);
        if (frm.doc.coverage_start) {
            setCoverageEnd(frm);
        }
    },
});


// ========================================================================
// 🔧 FUNKCJE POMOCNICZE
// ========================================================================

// 🔹 Przetwarzanie OCR z zapisanego dokumentu (po stronie serwera)
function processOcrFile(frm) {
    if (!frm.doc.name || frm.doc.__islocal) {
        frappe.msgprint(__("💾 Zapisz dokument przed przetwarzaniem OCR."));
        return;
    }

    frappe.call({
        method: "agencik.policy.doctype.insurance_policy.policy_ocr.process_policy_file",
        args: { docname: frm.doc.name },
        freeze: true,
        freeze_message: __("⏳ Trwa analiza dokumentu PDF przez OCR..."),
        callback: function (r) {
            console.log("📘 OCR response:", r);
            if (r.message && r.message.success && r.message.data) {
                fillFormWithOcrData(frm, r.message.data);
                frappe.show_alert({
                    message: __("📋 Dane z OCR zostały wypełnione. Zapisz dokument ręcznie."),
                    indicator: "green"
                });
            } else {
                frappe.msgprint(__("❌ Nie udało się przetworzyć dokumentu OCR."));
            }
        }
    });
}


// 🔹 Uzupełnianie danych w formularzu z OCR
function fillFormWithOcrData(frm, data) {
    if (!data) return;

    const mappings = {
        policy_number: "Numer polisy",
        insurance_company: "Towarzystwo",
        client: "Klient",
        vehicle: "Pojazd",
        coverage_start: "Początek ochrony",
    };

    // ✅ Uzupełnienie pól (tylko jeśli dane są prawidłowe)
    if (data.policy_number) frm.set_value("policy_number", cleanText(data.policy_number));
    if (data.insurance_company) frm.set_value("insurance_company", cleanText(data.insurance_company));
    if (data.client) frm.set_value("client", cleanText(data.client));
    if (data.vehicle) frm.set_value("vehicle", cleanVehicle(data.vehicle));
    if (data.vehicle_type) frm.set_value("vehicle_type", cleanVehicle(data.vehicle_type));
    if (data.vin) frm.set_value("vin", cleanText(data.vin));

    // 🔹 Walidacja i ustawienie dat
    if (isValidDate(data.coverage_start)) {
        frm.set_value("coverage_start", formatDate(data.coverage_start));
    }

    frm.refresh_fields();
}


// 🔹 Czyszczenie numeru rejestracyjnego
function cleanVehicle(text) {
    if (!text) return "";
    return text
        // .replace(/nr rejestracyjny[:\s]*/i, "")
        // .replace(/rejestracyjny/i, "")
        .replace(/nr/i, " ")
    // .replace(/\s+/g, "")
    // .trim()
    // .toUpperCase();
}


// 🔹 Proste czyszczenie tekstu
function cleanText(text) {
    if (!text) return "";
    return text.replace(/[\n\r]+/g, " ").trim();
}


// 🔹 Sprawdzenie poprawności daty (YYYY-MM-DD)
function isValidDate(str) {
    if (!str) return false;
    const d = new Date(str);
    return !isNaN(d.getTime());
}


// 🔹 Formatowanie daty do formatu ERPNext
function formatDate(dateStr) {
    if (!dateStr) return "";
    return frappe.datetime.obj_to_str(frappe.datetime.str_to_obj(dateStr));
}


// 🔹 Obliczanie prowizji
function calculateCommission(frm) {
    if (!frm.doc.insurance_components || frm.doc.insurance_components.length === 0) {
        frm.set_value("commission_vehicle", 0);
        frm.refresh_field("commission_vehicle");
        frappe.msgprint(__("Najpierw wybierz co najmniej jeden komponent ubezpieczenia."));
        return;
    }

    frm.call("calculate_commission_api").then(r => {
        if (r.message) {
            const commission_amount = r.message.commission;
            const components_count = r.message.components_count;

            frm.refresh_field("commission_vehicle");
            frappe.show_alert({
                message: __("💰 Prowizja: {0} (na podstawie {1} komponentów)",
                    [format_currency(commission_amount), components_count]),
                indicator: "green"
            });
        }
    }).catch(err => {
        console.error("Error calculating commission:", err);
        frappe.msgprint(__("Błąd podczas obliczania prowizji."));
    });
}


// 🔹 Ustaw coverage_end na rok po coverage_start
function setCoverageEnd(frm) {
    if (!frm.doc.coverage_start) return;
    const startDate = frappe.datetime.str_to_obj(frm.doc.coverage_start);
    if (!startDate) return;

    const endDate = new Date(startDate);
    endDate.setFullYear(endDate.getFullYear() + 1);
    endDate.setDate(endDate.getDate() - 1);

    frm.set_value("coverage_end", frappe.datetime.obj_to_str(endDate));
    console.log("📅 coverage_end ustawione na:", frm.doc.coverage_end);
}
