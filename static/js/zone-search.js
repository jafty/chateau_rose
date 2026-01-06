(function () {
    const debounce = (fn, delay = 250) => {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    };

    const buildDatalist = (input) => {
        const list = document.createElement('datalist');
        const listId = `zone-options-${Math.random().toString(36).slice(2)}`;
        list.id = listId;
        input.setAttribute('list', listId);
        return list;
    };

    const populateOptions = (datalist, results, labelField, valueField) => {
        datalist.innerHTML = '';
        results.forEach((item) => {
            const option = document.createElement('option');
            const label = item[labelField] ?? '';
            option.value = label;
            option.dataset.value = item[valueField] ?? '';
            option.dataset.label = label;
            datalist.appendChild(option);
        });
    };

    const initZoneSearch = (select) => {
        const searchUrl = select.dataset.zoneSearchUrl;
        if (!searchUrl) return;

        const labelField = select.dataset.zoneLabelField || 'name';
        const valueField = select.dataset.zoneValueField || 'id';
        const placeholder = select.dataset.zoneSearchPlaceholder || 'Rechercher une zone';

        const allowedValues = Array.from(select.options)
            .map((option) => option.value)
            .filter((value) => value !== '');

        const hiddenInput = document.createElement('input');
        hiddenInput.type = 'hidden';
        hiddenInput.name = select.name;
        hiddenInput.value = select.value;
        hiddenInput.required = select.required;

        const wrapper = document.createElement('div');
        wrapper.className = 'zone-search';

        const textInput = document.createElement('input');
        textInput.type = 'search';
        textInput.placeholder = placeholder;
        textInput.autocomplete = 'off';
        textInput.className = 'zone-search__input';

        const datalist = buildDatalist(textInput);
        wrapper.appendChild(textInput);
        wrapper.appendChild(datalist);
        wrapper.appendChild(hiddenInput);

        const selectedOption = select.options[select.selectedIndex];
        const hasSelectedValue = selectedOption && selectedOption.value !== '';
        if (hasSelectedValue) {
            textInput.value = selectedOption.textContent;
            hiddenInput.value = selectedOption.value;
        }

        select.name = '';
        select.hidden = true;
        select.setAttribute('aria-hidden', 'true');
        select.after(wrapper);

        const fetchResults = debounce((term) => {
            const url = new URL(searchUrl, window.location.origin);
            if (term) {
                url.searchParams.set('q', term);
            }
            fetch(url.toString(), { headers: { Accept: 'application/json' } })
                .then((response) => response.json())
                .then((data) => {
                    const results = Array.isArray(data.results) ? data.results : [];
                    const filteredResults = allowedValues.length
                        ? results.filter((item) => allowedValues.includes(String(item[valueField] ?? '')))
                        : results;
                    populateOptions(datalist, filteredResults, labelField, valueField);
                })
                .catch(() => {
                    datalist.innerHTML = '';
                });
        }, 250);

        textInput.addEventListener('input', (event) => {
            hiddenInput.value = '';
            fetchResults(event.target.value.trim());
        });

        textInput.addEventListener('change', () => {
            const match = Array.from(datalist.options).find((option) => option.value === textInput.value);
            hiddenInput.value = match ? match.dataset.value || match.value : '';
        });

        fetchResults('');
    };

    document.addEventListener('DOMContentLoaded', () => {
        const zoneSelects = document.querySelectorAll('select[data-zone-search-url]');
        zoneSelects.forEach(initZoneSearch);
    });
})();
