(() => {
  "use strict";

  const STORAGE_KEY = "jisr.reports.v1";
  const STATUSES = ["جديد", "تم الاستلام", "قيد الإصلاح", "بانتظار قطع غيار", "تم الإصلاح"];
  const DEPARTMENTS = ["الطوارئ", "العناية المركزة", "العمليات", "الأشعة", "المختبر", "غسيل الكلى", "عيادة الباطنية", "عيادة الأطفال", "عيادة الأسنان", "عيادة العيون"];
  const PRIORITY_ORDER = { critical: 0, medium: 1, low: 2 };
  const PRIORITY_LABELS = { critical: "حرج", medium: "متوسط", low: "منخفض" };
  const $ = (selector, root = document) => root.querySelector(selector);
  const app = $("#app-main");
  let activeRole = "clinician";
  let currentFilters = { status: "", department: "" };

  const now = Date.now();
  const hoursAgo = (hours) => new Date(now - hours * 3600000).toISOString();
  function seedReports() {
    const examples = [
      { id: "JSR-260401", department: "العناية المركزة", equipment: "جهاز تنفس صناعي", equipmentNumber: "ICU-VENT-04", description: "إنذار متكرر لانخفاض ضغط الدائرة رغم تبديل الأنبوب وإعادة تشغيل الجهاز.", reporter: "سارة العتيبي", extension: "2418", risk: "yes", replacement: "no", status: "جديد", age: 1.2, reply: "", priorityOverride: null },
      { id: "JSR-260402", department: "الأشعة", equipment: "جهاز أشعة متنقل", equipmentNumber: "RAD-MOB-12", description: "تعذر تحريك ذراع الجهاز، ويظهر رمز خطأ عند بدء الفحص.", reporter: "خالد الحربي", extension: "3361", risk: "yes", replacement: "yes", status: "تم الاستلام", age: 4.5, reply: "تم استلام البلاغ، والفني في طريقه إلى القسم.", priorityOverride: null },
      { id: "JSR-260403", department: "المختبر", equipment: "محلل كيمياء حيوية", equipmentNumber: "", description: "تظهر قراءة غير مستقرة لمسبار الحرارة بعد المعايرة.", reporter: "نورة السالم", extension: "1852", risk: "no", replacement: "yes", status: "قيد الإصلاح", age: 8, reply: "جارٍ فحص وحدة التحكم الحراري.", priorityOverride: null },
      { id: "JSR-260404", department: "الطوارئ", equipment: "مضخة حقن", equipmentNumber: "ER-INF-08", description: "تعطل زر بدء الضخ أثناء الفحص الدوري.", reporter: "ريم القحطاني", extension: "1104", risk: "yes", replacement: "no", status: "بانتظار قطع غيار", age: 13, reply: "تم تحديد الخلل في لوحة التحكم. ننتظر وصول القطعة البديلة.", priorityOverride: null },
      { id: "JSR-260405", department: "العمليات", equipment: "جهاز تخدير", equipmentNumber: "OR-AN-03", description: "تمت صيانة حساس التدفق واختباره بنجاح.", reporter: "مازن الدوسري", extension: "2720", risk: "no", replacement: "yes", status: "تم الإصلاح", age: 27, reply: "اكتمل الإصلاح واجتاز الجهاز اختبار السلامة.", priorityOverride: null },
      { id: "JSR-260406", department: "عيادة الباطنية", equipment: "جهاز تخطيط قلب", equipmentNumber: "CV-ECG-06", description: "الطباعة تتوقف في منتصف التقرير بعد تبديل الورق.", reporter: "لمياء الزهراني", extension: "3095", risk: "no", replacement: "no", status: "جديد", age: 2.7, reply: "", priorityOverride: "medium" }
    ];
    return examples.map((item) => {
      const createdAt = hoursAgo(item.age);
      const statusHistory = STATUSES.slice(0, STATUSES.indexOf(item.status) + 1);
      const statusEvents = statusHistory.map((status, index) => ({
        status,
        at: index === 0
          ? createdAt
          : new Date(Date.parse(createdAt) + item.age * 3600000 * .72 * (index / (statusHistory.length - 1))).toISOString()
      }));
      return { ...item, createdAt, statusEvents, replies: item.reply ? [{ text: item.reply, at: hoursAgo(Math.max(.1, item.age - .6)) }] : [] };
    });
  }

  function getReports() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) {
          const migrated = parsed.map((report) =>
            report.id === "JSR-260406" &&
            report.reporter === "لمياء الزهراني" &&
            report.department === "قلب وأوعية دموية"
              ? { ...report, department: "عيادة الباطنية" }
              : report
          );
          if (migrated.some((report, index) => report !== parsed[index])) saveReports(migrated);
          return migrated;
        }
      }
      const seeded = seedReports();
      saveReports(seeded);
      return seeded;
    } catch (error) {
      console.error("تعذر قراءة البلاغات المحلية", error);
      return seedReports();
    }
  }
  function saveReports(reports) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(reports));
      return true;
    } catch (error) {
      toast("تعذر حفظ البيانات على هذا الجهاز. تحقق من مساحة التخزين.", "error");
      console.error(error);
      return false;
    }
  }
  let reports = getReports();

  function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
  }
  function classify(risk, replacement) {
    if (risk === "yes" && replacement === "no") return { key: "critical", reason: "الرعاية أو السلامة متأثرة، ولا يتوفر جهاز بديل؛ لذلك صُنّف البلاغ حرجاً." };
    if (risk === "yes" && replacement === "yes") return { key: "medium", reason: "الرعاية أو السلامة متأثرة، لكن يتوفر جهاز بديل؛ لذلك صُنّف البلاغ متوسطاً." };
    if (risk === "no") return { key: "low", reason: "لا يوجد توقف أو خطر على الرعاية، لذا صُنّف البلاغ منخفضاً." };
    return { key: "low", reason: "أجب عن السؤالين لاحتساب أولوية البلاغ تلقائياً." };
  }
  function priorityOf(report) { return report.priorityOverride || classify(report.risk, report.replacement).key; }
  function statusClass(status) {
    if (status === "تم الإصلاح") return "done";
    if (status === "بانتظار قطع غيار") return "waiting";
    return "";
  }
  function badge(priority) { return `<span class="severity-badge ${priority}">${PRIORITY_LABELS[priority]}</span>`; }
  function formatDate(iso, includeTime = true) {
    if (!iso) return "—";
    const date = new Date(iso);
    return new Intl.DateTimeFormat("ar-SA-u-ca-gregory", includeTime ? { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" } : { day: "numeric", month: "long", year: "numeric" }).format(date);
  }
  function relativeTime(iso) {
    const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
    if (minutes < 60) return `منذ ${minutes} د`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `منذ ${hours} س`;
    return `منذ ${Math.floor(hours / 24)} يوم`;
  }
  function toast(message, type = "") {
    const region = $("#toast-region");
    if (!region) return;
    const node = document.createElement("div");
    node.className = `toast ${type}`;
    node.textContent = message;
    region.append(node);
    window.setTimeout(() => node.remove(), 3600);
  }
  function commit() { saveReports(reports); render(); }
  function icon(name) {
    const paths = {
      plus: '<path d="M12 5v14M5 12h14"/>',
      shield: '<path d="M12 3 20 6v5c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V6l8-3Z"/><path d="m9 12 2 2 4-4"/>',
      wrench: '<path d="M14.5 6.5a5 5 0 0 0-6.2 6.2l-5.1 5.1a2 2 0 0 0 2.8 2.8l5.1-5.1a5 5 0 0 0 6.2-6.2l-3 3-3-3 3.2-2.8Z"/>',
      inbox: '<path d="M4 4h16v16H4z"/><path d="M4 13h4l2 3h4l2-3h4"/>',
      clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'
    };
    return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.inbox}</svg>`;
  }
  function render() {
    app.classList.remove("page-enter");
    app.innerHTML = activeRole === "clinician" ? renderClinician() : renderEngineering();
    void app.offsetWidth;
    app.classList.add("page-enter");
    if (activeRole === "clinician") bindForm();
    else bindEngineering();
  }
  function renderClinician() {
    const latest = [...reports].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    return `<section class="page-head">
      <div><h1>أبلغ عن تعطل جهاز</h1><p class="subhead">تفاصيل واضحة تصل مباشرة إلى فريق الهندسة الطبية.</p></div>
      <div class="head-note">${icon("shield")}<span>نموذج قصير · أقل من دقيقة</span></div>
    </section>
    <section class="clinician-layout">
      <form class="panel report-form" id="report-form" novalidate>
        <div class="section-title"><div><h2>بيانات البلاغ</h2><p>املأ الحقول المطلوبة لبدء المتابعة.</p></div></div>
        <div class="form-grid">
          <div class="field"><label for="department">القسم / العيادة <span class="required">*</span></label><select id="department" name="department" required><option value="" selected disabled>اختر القسم أو العيادة</option>${DEPARTMENTS.map((department) => `<option value="${escapeHTML(department)}">${escapeHTML(department)}</option>`).join("")}</select></div>
          <div class="field"><label for="equipment">اسم الجهاز <span class="required">*</span></label><input id="equipment" name="equipment" required placeholder="مثال: جهاز تنفس صناعي" /></div>
          <div class="field"><label for="equipment-number">رقم الجهاز <span class="optional-hint">اختياري</span></label><input id="equipment-number" name="equipmentNumber" placeholder="مثال: ICU-04" /></div>
          <div class="field"><label for="reporter">اسم المبلّغ <span class="required">*</span></label><input id="reporter" name="reporter" required autocomplete="name" placeholder="الاسم" /></div>
          <div class="field"><label for="extension">التحويلة <span class="required">*</span></label><input id="extension" name="extension" required inputmode="tel" placeholder="رقم التحويلة" /></div>
          <div class="field field-wide"><label for="description">وصف العطل <span class="required">*</span></label><textarea id="description" name="description" required maxlength="500" placeholder="ما الذي حدث؟ اذكر الرسالة أو السلوك الظاهر على الجهاز."></textarea></div>
          <div class="question-card"><div class="question-title"><span class="field-label">هل توقفت الرعاية أو أصبحت السلامة في خطر؟ <span class="required">*</span></span><span class="question-mark" aria-hidden="true">؟</span></div><div class="radio-options"><label class="radio-option"><input type="radio" name="risk" value="yes" required /><span>نعم</span></label><label class="radio-option"><input type="radio" name="risk" value="no" required /><span>لا</span></label></div></div>
          <div class="question-card"><div class="question-title"><span class="field-label">هل يتوفر جهاز بديل؟ <span class="required">*</span></span><span class="question-mark" aria-hidden="true">؟</span></div><div class="radio-options"><label class="radio-option"><input type="radio" name="replacement" value="yes" required /><span>نعم</span></label><label class="radio-option"><input type="radio" name="replacement" value="no" required /><span>لا</span></label></div></div>
        </div>
        <div class="severity-preview" id="severity-preview" aria-live="polite">${icon("shield")}<div class="severity-copy"><strong>الأولوية: بانتظار الإجابات</strong><p>أجب عن السؤالين لتظهر الأولوية وتفسيرها قبل الإرسال.</p></div></div>
        <div class="form-actions"><p class="form-caption"><span class="required">*</span> حقول مطلوبة · أدخل بيانات الجهاز والتواصل المطلوبة فقط.</p><button class="button-primary" type="submit">إرسال البلاغ ${icon("plus")}</button></div>
      </form>
      <section class="panel list-panel" aria-labelledby="my-reports-title">
        <div class="list-heading"><div><h2 id="my-reports-title">بلاغاتي</h2><p>عرض تجريبي مشترك على هذا الجهاز</p></div><span class="count-pill">${latest.length}</span></div>
        <div class="reports-list">${latest.length ? latest.map(renderClinicianCard).join("") : emptyState("لا توجد بلاغات بعد", "أرسل أول بلاغ ليظهر هنا.")}
        </div>
      </section>
    </section>`;
  }
  function renderClinicianCard(report) {
    const latestReply = report.replies?.at(-1);
    return `<article class="report-card">
      <div class="report-topline"><span class="report-id">${escapeHTML(report.id)}</span>${badge(priorityOf(report))}</div>
      <h3 class="report-title">${escapeHTML(report.equipment)}</h3>
      <div class="report-meta"><span>${escapeHTML(report.department)}</span><i class="meta-dot"></i><span class="status-badge ${statusClass(report.status)}">${escapeHTML(report.status)}</span><i class="meta-dot"></i><span>${relativeTime(report.createdAt)}</span></div>
      ${latestReply ? `<div class="reply-preview"><strong>آخر رد من الهندسة · ${formatDate(latestReply.at)}</strong><p>${escapeHTML(latestReply.text)}</p></div>` : `<div class="report-meta"><span>بانتظار تحديث فريق الهندسة الطبية</span></div>`}
    </article>`;
  }
  function emptyState(title, copy) {
    return `<div class="empty-state"><span class="empty-symbol">${icon("inbox")}</span><strong>${title}</strong><p>${copy}</p></div>`;
  }
  function updateSeverityPreview() {
    const risk = $('input[name="risk"]:checked', app)?.value;
    const replacement = $('input[name="replacement"]:checked', app)?.value;
    const preview = $("#severity-preview", app);
    if (!preview) return;
    const result = classify(risk, replacement);
    const waiting = !risk || !replacement;
    preview.className = `severity-preview ${waiting ? "" : `severity-${result.key}`}`;
    preview.innerHTML = `${icon(result.key === "critical" ? "wrench" : "shield")}<div class="severity-copy"><strong>${waiting ? "الأولوية: بانتظار الإجابات" : `الأولوية التلقائية: ${PRIORITY_LABELS[result.key]}`}</strong><p>${result.reason}</p></div>`;
  }
  function bindForm() {
    const form = $("#report-form", app);
    form.addEventListener("change", updateSeverityPreview);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!form.reportValidity()) {
        const firstInvalid = form.querySelector(":invalid");
        firstInvalid?.focus();
        toast("أكمل الحقول المطلوبة والإجابات قبل إرسال البلاغ.", "error");
        return;
      }
      const emptyRequired = [...form.querySelectorAll('input[required]:not([type="radio"]), textarea[required]')]
        .find((field) => !field.value.trim());
      if (emptyRequired) {
        emptyRequired.focus();
        toast("أدخل قيمة في جميع الحقول المطلوبة.", "error");
        return;
      }
      const data = new FormData(form);
      const createdAt = new Date().toISOString();
      const report = {
        id: makeReportId(), department: data.get("department").trim(), equipment: data.get("equipment").trim(),
        equipmentNumber: data.get("equipmentNumber").trim(), description: data.get("description").trim(),
        reporter: data.get("reporter").trim(), extension: data.get("extension").trim(),
        risk: data.get("risk"), replacement: data.get("replacement"), status: "جديد",
        createdAt, statusEvents: [{ status: "جديد", at: createdAt }], replies: [], priorityOverride: null
      };
      reports.unshift(report);
      if (!saveReports(reports)) { reports.shift(); return; }
      render();
      toast(`تم إرسال البلاغ بنجاح · رقم البلاغ ${report.id}`);
      app.focus();
    });
  }
  function makeReportId() {
    const date = new Date();
    const stamp = `${String(date.getFullYear()).slice(-2)}${String(date.getMonth() + 1).padStart(2, "0")}${String(date.getDate()).padStart(2, "0")}`;
    let id;
    do { id = `JSR-${stamp}-${Math.random().toString(36).slice(2, 5).toUpperCase()}`; } while (reports.some((report) => report.id === id));
    return id;
  }
  function renderEngineering() {
    const sorted = [...reports].sort((a, b) => PRIORITY_ORDER[priorityOf(a)] - PRIORITY_ORDER[priorityOf(b)] || new Date(a.createdAt) - new Date(b.createdAt));
    const openCount = reports.filter((report) => report.status !== "تم الإصلاح").length;
    const receiveTimes = reports.map((report) => {
      const firstChange = report.statusEvents?.find((event) => event.status !== "جديد");
      return firstChange ? (new Date(firstChange.at) - new Date(report.createdAt)) / 60000 : null;
    }).filter((n) => n !== null && n >= 0);
    const repairTimes = reports.filter((report) => report.status === "تم الإصلاح").map((report) => {
      const event = [...(report.statusEvents || [])].reverse().find((item) => item.status === "تم الإصلاح");
      return event ? (new Date(event.at) - new Date(report.createdAt)) / 3600000 : null;
    }).filter((n) => n !== null && n >= 0);
    const avgReceive = receiveTimes.length ? `${(receiveTimes.reduce((a, b) => a + b, 0) / receiveTimes.length).toFixed(0)}` : "—";
    const avgRepair = repairTimes.length ? `${(repairTimes.reduce((a, b) => a + b, 0) / repairTimes.length).toFixed(1)}` : "—";
    const departments = [...new Set(reports.map((report) => report.department))].sort((a, b) => a.localeCompare(b, "ar"));
    const visible = sorted.filter((report) => (!currentFilters.status || report.status === currentFilters.status) && (!currentFilters.department || report.department === currentFilters.department));
    return `<section class="page-head engineering-head"><div><h1>لوحة الهندسة الطبية</h1><p class="subhead">رتّب الأولويات، سجّل التحديثات، وتابع حالة كل جهاز.</p></div><div class="head-note">${icon("wrench")}<span>الأولوية أولاً · ثم الأقدم</span></div></section>
      <section class="engineering-layout">
        <div class="metric-grid" aria-label="مؤشرات البلاغات">
          <article class="metric-card critical-metric"><span class="metric-label">بلاغات مفتوحة</span><strong class="metric-value">${openCount}<small>بلاغ</small></strong></article>
          <article class="metric-card"><span class="metric-label">متوسط زمن الاستلام</span><strong class="metric-value">${avgReceive}<small>دقيقة</small></strong></article>
          <article class="metric-card"><span class="metric-label">متوسط زمن الإصلاح</span><strong class="metric-value">${avgRepair}<small>ساعة</small></strong></article>
        </div>
        <section class="panel workspace-panel" aria-labelledby="queue-title">
          <div class="workspace-toolbar"><div><h2 id="queue-title">قائمة البلاغات</h2><p>${visible.length} من ${reports.length} بلاغ · مرتبة حسب الأولوية ثم وقت الإرسال</p></div>
            <div class="filters"><label class="sr-only" for="status-filter">تصفية حسب الحالة</label><select id="status-filter" class="filter-select"><option value="">كل الحالات</option>${STATUSES.map((status) => `<option value="${escapeHTML(status)}" ${currentFilters.status === status ? "selected" : ""}>${escapeHTML(status)}</option>`).join("")}</select>
              <label class="sr-only" for="department-filter">تصفية حسب القسم</label><select id="department-filter" class="filter-select"><option value="">كل الأقسام</option>${departments.map((department) => `<option value="${escapeHTML(department)}" ${currentFilters.department === department ? "selected" : ""}>${escapeHTML(department)}</option>`).join("")}</select>
            </div>
          </div>
          <div class="engineering-list">${visible.length ? visible.map(renderEngineeringCard).join("") : emptyState("لا توجد بلاغات مطابقة", "غيّر محددات التصفية لعرض بلاغات أخرى.")}</div>
        </section>
      </section>`;
  }
  function renderEngineeringCard(report) {
    const automatic = classify(report.risk, report.replacement);
    const statusHistory = (report.statusEvents || []).map((event) => `${escapeHTML(event.status)} · ${formatDate(event.at)}`).join(" ← ");
    const replies = report.replies || [];
    return `<article class="engineering-card" data-report-id="${escapeHTML(report.id)}">
      <div class="engineering-card-main">
        <div class="report-topline"><span class="report-id">${escapeHTML(report.id)}</span>${badge(priorityOf(report))}<span class="status-badge ${statusClass(report.status)}">${escapeHTML(report.status)}</span></div>
        <div class="engineering-card-title-row"><h3>${escapeHTML(report.equipment)}</h3><span class="meta-dot"></span><span class="report-meta">${escapeHTML(report.department)}</span></div>
        <p class="engineering-description">${escapeHTML(report.description)}</p>
        <div class="engineering-meta"><span>المبلّغ: ${escapeHTML(report.reporter)}</span><span>التحويلة: ${escapeHTML(report.extension)}</span><span>رقم الجهاز: ${escapeHTML(report.equipmentNumber || "غير محدد")}</span><span>${formatDate(report.createdAt)} · ${relativeTime(report.createdAt)}</span></div>
        <div class="auto-severity" style="margin-top:10px">التصنيف التلقائي الأصلي ${badge(automatic.key)} <span>— ${escapeHTML(automatic.reason)}</span></div>
        ${replies.length ? `<div class="reply-preview"><strong>آخر تحديث مسجل · ${formatDate(replies.at(-1).at)}</strong><p>${escapeHTML(replies.at(-1).text)}</p></div>` : ""}
        <div class="history-note"><strong>سجل الحالة:</strong> ${statusHistory}</div>
      </div>
      <div class="engineering-side">
        <div><label class="control-label" for="severity-${escapeHTML(report.id)}">تعديل الأولوية يدوياً</label><div class="severity-control"><select class="severity-select" id="severity-${escapeHTML(report.id)}" data-action="severity" aria-label="تعديل أولوية ${escapeHTML(report.id)}"><option value="auto" ${!report.priorityOverride ? "selected" : ""}>تلقائي · ${PRIORITY_LABELS[automatic.key]}</option><option value="critical" ${report.priorityOverride === "critical" ? "selected" : ""}>حرج</option><option value="medium" ${report.priorityOverride === "medium" ? "selected" : ""}>متوسط</option><option value="low" ${report.priorityOverride === "low" ? "selected" : ""}>منخفض</option></select></div></div>
        <div><label class="control-label" for="status-${escapeHTML(report.id)}">تحديث الحالة</label><select class="severity-select status-select" id="status-${escapeHTML(report.id)}" data-action="status" aria-label="تحديث حالة البلاغ ${escapeHTML(report.id)}">${STATUSES.map((status) => `<option value="${escapeHTML(status)}" ${report.status === status ? "selected" : ""}>${escapeHTML(status)}</option>`).join("")}</select></div>
        <form class="reply-row" data-action="reply"><label class="sr-only" for="reply-${escapeHTML(report.id)}">إضافة رد أو ملاحظة</label><input id="reply-${escapeHTML(report.id)}" class="reply-input" name="reply" maxlength="300" placeholder="رد أو ملاحظة للفريق..." required /><button type="submit" class="button-secondary">إضافة</button></form>
      </div>
    </article>`;
  }
  function bindEngineering() {
    $("#status-filter", app).addEventListener("change", (event) => { currentFilters.status = event.target.value; render(); });
    $("#department-filter", app).addEventListener("change", (event) => { currentFilters.department = event.target.value; render(); });
    app.onchange = handleEngineeringChange;
    app.onsubmit = handleEngineeringSubmit;
  }
  function findReportFrom(node) {
    const card = node.closest("[data-report-id]");
    return card ? reports.find((report) => report.id === card.dataset.reportId) : null;
  }
  function handleEngineeringChange(event) {
    const control = event.target;
    const report = findReportFrom(control);
    if (!report) return;
    if (control.dataset.action === "status") {
      if (control.value === report.status) return;
      report.status = control.value;
      report.statusEvents ||= [];
      report.statusEvents.push({ status: report.status, at: new Date().toISOString() });
      commit();
      toast(`تم تحديث الحالة إلى «${report.status}».`);
      return;
    }
    if (control.dataset.action !== "severity") return;
    report.priorityOverride = control.value === "auto" ? null : control.value;
    commit();
    toast(report.priorityOverride ? "تم حفظ الأولوية المعدّلة، والتصنيف التلقائي الأصلي محفوظ." : "عادت الأولوية إلى التصنيف التلقائي.");
  }
  function handleEngineeringSubmit(event) {
    const form = event.target.closest('form[data-action="reply"]');
    if (!form) return;
    event.preventDefault();
    const report = findReportFrom(form);
    const input = form.elements.reply;
    const text = input.value.trim();
    if (!text || !report) { input.focus(); return; }
    report.replies ||= [];
    report.replies.push({ text, at: new Date().toISOString() });
    commit();
    toast("أضيفت الملاحظة إلى سجل البلاغ.");
  }
  document.querySelectorAll(".role-button").forEach((button) => button.addEventListener("click", () => {
    activeRole = button.dataset.role;
    document.querySelectorAll(".role-button").forEach((item) => {
      const active = item === button;
      item.classList.toggle("is-active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    render();
    app.focus();
  }));
  const todayLabel = $("#today-label");
  todayLabel.textContent = new Intl.DateTimeFormat("ar-SA-u-ca-gregory", { weekday: "long", day: "numeric", month: "long" }).format(new Date());
  render();
})();