"""JavaScript-based form extractor: runs in-page to extract form structure.

All DOM interaction is in JavaScript so the Python layer stays clean.
"""

# JavaScript that runs inside the page and returns form structure as JSON.
# Returns: list of field dicts with id, name, label, type, required, options, selector.
FORM_EXTRACTOR_JS = """
() => {
  const form = document.querySelector('form') || document.body;

  function getLabel(el) {
    // 1. label[for=id]
    if (el.id) {
      const lbl = document.querySelector(`label[for="${el.id}"]`);
      if (lbl) return lbl.textContent.trim();
    }
    // 2. aria-label
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim();
    // 3. aria-labelledby
    const labelledby = el.getAttribute('aria-labelledby');
    if (labelledby) {
      const lblEl = document.getElementById(labelledby);
      if (lblEl) return lblEl.textContent.trim();
    }
    // 4. placeholder as fallback
    if (el.placeholder) return el.placeholder.trim();
    // 5. parent label
    if (el.closest('label')) return el.closest('label').textContent.replace(el.value || '', '').trim();
    // 6. nearest preceding text sibling
    let prev = el.previousElementSibling;
    while (prev) {
      const txt = prev.textContent.trim();
      if (txt.length > 0 && txt.length < 120) return txt;
      prev = prev.previousElementSibling;
    }
    return el.name || el.id || '';
  }

  function getSectionTitle(el) {
    const fieldset = el.closest('fieldset');
    if (fieldset) {
      const legend = fieldset.querySelector('legend');
      if (legend) return legend.textContent.trim();
    }
    const section = el.closest('section, [class*="section"], [class*="group"]');
    if (section) {
      const heading = section.querySelector('h1, h2, h3, h4, h5, h6');
      if (heading) return heading.textContent.trim();
    }
    return null;
  }

  function getCssSelector(el) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    if (el.name) return `[name="${CSS.escape(el.name)}"]`;
    // fallback: tag + index among siblings
    const siblings = Array.from(el.parentElement.children);
    const idx = siblings.indexOf(el);
    return `${el.tagName.toLowerCase()}:nth-child(${idx + 1})`;
  }

  function getOptions(el) {
    if (el.tagName === 'SELECT') {
      return Array.from(el.options)
        .filter(o => o.value !== '' && o.value !== null)
        .map(o => o.text.trim());
    }
    return null;
  }

  const inputs = Array.from(form.querySelectorAll(
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]), select, textarea'
  ));

  const fields = inputs.map((el, idx) => {
    const type = el.type || el.tagName.toLowerCase();
    return {
      field_id: el.id || el.name || `field_${idx}`,
      name: el.name || el.id || `field_${idx}`,
      label: getLabel(el),
      field_type: (el.tagName === 'SELECT') ? 'select' : (el.tagName === 'TEXTAREA' ? 'textarea' : type),
      is_required: el.required || el.getAttribute('aria-required') === 'true',
      options: getOptions(el),
      placeholder: el.placeholder || null,
      css_selector: getCssSelector(el),
      section_title: getSectionTitle(el),
      aria_label: el.getAttribute('aria-label') || null,
    };
  });

  // Find submit button
  const submitBtn = form.querySelector(
    'button[type="submit"], input[type="submit"], button:not([type])'
  );
  const submitSelector = submitBtn && submitBtn.id
    ? `#${CSS.escape(submitBtn.id)}`
    : (submitBtn ? submitBtn.tagName.toLowerCase() + '[type="submit"]' : 'button[type="submit"]');

  // Extract sections from fieldsets / headings
  const sections = [];
  const fieldsetEls = form.querySelectorAll('fieldset');
  if (fieldsetEls.length > 0) {
    fieldsetEls.forEach(fs => {
      const legend = fs.querySelector('legend');
      sections.push({ title: legend ? legend.textContent.trim() : null });
    });
  }

  return {
    fields,
    page_title: document.title || null,
    submit_button_selector: submitSelector,
    form_action: (form.tagName === 'FORM' ? form.action : null) || null,
    sections: sections,
  };
}
"""

# JavaScript to detect common confirmation page patterns
# Raw string: backslashes pass through to JavaScript regex engine unchanged
CONFIRMATION_DETECTOR_JS = r"""
() => {
  const text = document.body.innerText.toLowerCase();
  const patterns = [
    'application submitted',
    'application received',
    'thank you for applying',
    'your application has been',
    'successfully submitted',
    'application reference',
    'confirmation number',
    'application id',
    'we have received your',
  ];
  const matched = patterns.some(p => text.includes(p));

  // Try to extract a confirmation ID / reference number
  const refPatterns = [
    /\b(app[-_]?[a-z0-9]+)\b/i,
    /\b(ref[-_:]?\s*[A-Z0-9]{6,})\b/i,
    /reference[:\s]+([A-Z0-9-]{4,})/i,
    /confirmation[:\s]+([A-Z0-9-]{4,})/i,
    /application\s+(?:id|number|#)[:\s]+([A-Z0-9-]{4,})/i,
  ];
  let confirmationId = null;
  for (const pattern of refPatterns) {
    const m = text.match(pattern);
    if (m) { confirmationId = m[1].trim(); break; }
  }

  return { is_confirmation: matched, confirmation_id: confirmationId, page_text: text.slice(0, 2000) };
}
"""
