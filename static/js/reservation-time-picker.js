(function () {
  'use strict';

  window.createReservationTimePicker = function (root, fields, doneButton, onDurationPreview) {
    var title = root.querySelector('[data-time-title]');
    var preview = root.querySelector('[data-time-preview]');
    var error = root.querySelector('[data-time-error]');
    var groups = Array.from(root.querySelectorAll('[data-time-options]'));
    var activeIndex = -1;
    var draft;

    function pad(value) { return String(value).padStart(2, '0'); }

    function parse(value) {
      if (!value) return null;
      var parts = value.split(':').map(Number);
      return { hour: parts[0] % 12 || 12, minute: parts[1], period: parts[0] >= 12 ? 'PM' : 'AM' };
    }

    function timeValue(time) {
      return pad(time.hour % 12 + (time.period === 'PM' ? 12 : 0)) + ':' + pad(time.minute);
    }

    function display(time) { return pad(time.hour) + ':' + pad(time.minute) + ' ' + time.period; }

    function refresh() {
      fields.forEach(function (field) {
        var time = parse(field.input.value);
        field.trigger.querySelector('[data-time-display]').textContent = time ? display(time) : 'Choose time';
        field.trigger.classList.toggle('has-value', Boolean(time));
        var invalid = field.input.classList.contains('is-invalid');
        field.trigger.classList.toggle('is-invalid', invalid);
        if (invalid) field.trigger.setAttribute('aria-invalid', 'true');
        else field.trigger.removeAttribute('aria-invalid');
        if (field.input.hasAttribute('aria-describedby')) {
          field.trigger.setAttribute('aria-describedby', field.input.getAttribute('aria-describedby'));
        } else field.trigger.removeAttribute('aria-describedby');
      });
    }

    function render() {
      preview.textContent = display(draft);
      groups.forEach(function (group) {
        var name = group.dataset.timeOptions;
        group.querySelectorAll('[data-time-value]').forEach(function (button) {
          var selected = String(draft[name]) === button.dataset.timeValue;
          button.classList.toggle('is-selected', selected);
          button.setAttribute('aria-pressed', String(selected));
          button.tabIndex = selected ? 0 : -1;
        });
      });
      if (typeof onDurationPreview === 'function') {
        var values = fields.map(function (field) { return field.input.value; });
        values[activeIndex] = timeValue(draft);
        onDurationPreview(values[0], values[1], true);
      }
    }

    function centerSelection(group) {
      var selected = group.querySelector('.is-selected');
      if (selected) group.scrollTop = Math.max(0, selected.offsetTop - (group.clientHeight - selected.offsetHeight) / 2);
    }

    function open(input) {
      activeIndex = fields.findIndex(function (field) { return field.input === input; });
      if (activeIndex < 0) return;
      var value = input.value;
      if (!value && activeIndex > 0 && fields[0].input.value) {
        var start = fields[0].input.value.split(':').map(Number);
        var minutes = Math.min(start[0] * 60 + start[1] + 60, 1439);
        value = pad(Math.floor(minutes / 60)) + ':' + pad(minutes % 60);
      }
      draft = parse(value || (activeIndex === 0 ? '09:00' : '10:00'));
      title.textContent = fields[activeIndex].title;
      error.hidden = true;
      root.hidden = false;
      doneButton.disabled = true;
      fields.forEach(function (field, index) {
        field.trigger.setAttribute('aria-expanded', String(index === activeIndex));
      });
      render();
      groups.forEach(centerSelection);
      groups[0].querySelector('.is-selected').focus({ preventScroll: true });
    }

    function close(restoreFocus) {
      var previous = fields[activeIndex];
      root.hidden = true;
      doneButton.disabled = false;
      fields.forEach(function (field) { field.trigger.setAttribute('aria-expanded', 'false'); });
      activeIndex = -1;
      if (typeof onDurationPreview === 'function') {
        onDurationPreview(fields[0].input.value, fields[1].input.value, false);
      }
      if (restoreFocus && previous) previous.trigger.focus();
    }

    function choose(button) {
      var group = button.closest('[data-time-options]');
      var name = group.dataset.timeOptions;
      draft[name] = name === 'period' ? button.dataset.timeValue : Number(button.dataset.timeValue);
      error.hidden = true;
      render();
    }

    groups.forEach(function (group) {
      var name = group.dataset.timeOptions;
      var values = name === 'period' ? ['AM', 'PM'] : Array.from({ length: name === 'hour' ? 12 : 60 }, function (_, index) {
        return name === 'hour' ? index + 1 : index;
      });
      values.forEach(function (value) {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'reservation-time-option';
        button.dataset.timeValue = value;
        button.textContent = name === 'period' ? value : pad(value);
        button.setAttribute('aria-label', name === 'period' ? value : value + (name === 'hour' ? ' hours' : ' minutes'));
        group.appendChild(button);
      });
      group.addEventListener('click', function (event) {
        var button = event.target.closest('[data-time-value]');
        if (button) choose(button);
      });
      group.addEventListener('keydown', function (event) {
        var buttons = Array.from(group.querySelectorAll('[data-time-value]'));
        var index = buttons.indexOf(event.target);
        if (index < 0) return;
        if (event.key === 'ArrowUp') index = Math.max(0, index - 1);
        else if (event.key === 'ArrowDown') index = Math.min(buttons.length - 1, index + 1);
        else if (event.key === 'Home') index = 0;
        else if (event.key === 'End') index = buttons.length - 1;
        else return;
        event.preventDefault();
        choose(buttons[index]);
        buttons[index].focus({ preventScroll: true });
        centerSelection(group);
      });
    });

    root.querySelector('[data-time-apply]').addEventListener('click', function () {
      var value = timeValue(draft);
      if (activeIndex > 0 && fields[0].input.value && value <= fields[0].input.value.slice(0, 5)) {
        error.textContent = 'End time must be later than start time.';
        error.hidden = false;
        return;
      }
      var input = fields[activeIndex].input;
      var chooseEnd = activeIndex === 0 && (!fields[1].input.value || fields[1].input.value.slice(0, 5) <= value);
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      close(false);
      if (chooseEnd) open(fields[1].input);
      else doneButton.focus();
    });
    root.querySelectorAll('[data-time-cancel]').forEach(function (button) {
      button.addEventListener('click', function () { close(true); });
    });
    root.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') {
        event.stopPropagation();
        event.preventDefault();
        close(true);
      }
    });

    fields.forEach(function (field) {
      field.trigger.addEventListener('click', function () {
        if (!root.hidden && fields[activeIndex] === field) close(true);
        else open(field.input);
      });
      field.input.addEventListener('change', refresh);
      field.input.hidden = true;
      field.trigger.hidden = false;
      field.label.htmlFor = field.trigger.id;
    });
    refresh();
    return { open: open, close: close, refresh: refresh };
  };
}());
