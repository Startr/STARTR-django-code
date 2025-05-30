from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.simple_tag
def smart_select_js():
    """
    Returns the JavaScript code for smart select functionality.
    """
    return mark_safe("""
    <script>
    function convertSelectToSmartSelect(originalSelect) {
        // Skip if already converted, hidden, or is a multiple select
        if (originalSelect.classList.contains('smart-select-converted') || 
            originalSelect.style.display === 'none' ||
            originalSelect.offsetParent === null ||
            originalSelect.multiple) {
            return;
        }
        
        originalSelect.classList.add('smart-select-converted');

        const wrapper = document.createElement('div');
        wrapper.className = 'smart-select-wrapper';

        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Type to filter...';
        input.setAttribute('autocomplete', 'off');
        input.className = 'smart-select-input';

        const list = document.createElement('ul');
        list.className = 'smart-options';
        list.style.display = 'none';  // Ensure hidden by default
        list.style.position = 'absolute';
        list.style.zIndex = '1001';
        list.style.width = '100%';
        list.style.maxHeight = '200px';
        list.style.overflowY = 'auto';
        list.style.backgroundColor = '#fff';
        list.style.border = '1px solid #ccc';
        list.style.padding = '0';

        // Create options from the original select, filtering out empty choices
        const options = Array.from(originalSelect.options)
            .filter(option => option.textContent.trim() !== '---------')
            .map(option => {
                const li = document.createElement('li');
                li.textContent = option.textContent;
                li.dataset.value = option.value;
                
                li.addEventListener('click', () => {
                    input.value = option.textContent;
                    originalSelect.value = option.value;
                    list.style.display = 'none';
                    
                    // Trigger change event on original select
                    const event = new Event('change', { bubbles: true });
                    originalSelect.dispatchEvent(event);
                });
                
                list.appendChild(li);
                return li;
            });

        // Set initial value only if an option is selected
        const selectedOption = originalSelect.options[originalSelect.selectedIndex];
        if (selectedOption && selectedOption.textContent.trim() !== '---------') {
            input.value = selectedOption.textContent;
        }

        // Handle input filtering
        input.addEventListener('input', () => {
            const query = input.value.toLowerCase();
            let visible = 0;
            
            options.forEach(li => {
                if (li.textContent.toLowerCase().includes(query)) {
                    li.style.display = 'block';
                    visible++;
                } else {
                    li.style.display = 'none';
                }
            });
            
            // Only show list if there are visible options and input is focused
            list.style.display = (visible && document.activeElement === input) ? 'block' : 'none';
        });

        // Show options on focus
        input.addEventListener('focus', () => {
            // Show all options when focused
            options.forEach(li => li.style.display = 'block');
            list.style.display = 'block';
        });

        // Hide options on blur
        input.addEventListener('blur', () => {
            setTimeout(() => {
                list.style.display = 'none';
            }, 200);
        });

        // Handle keyboard navigation
        input.addEventListener('keydown', (e) => {
            const visibleOptions = Array.from(list.children).filter(li => li.style.display !== 'none');
            const currentIndex = visibleOptions.findIndex(li => li.classList.contains('highlighted'));
            
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                const nextIndex = (currentIndex + 1) % visibleOptions.length;
                visibleOptions.forEach(li => li.classList.remove('highlighted'));
                visibleOptions[nextIndex].classList.add('highlighted');
                visibleOptions[nextIndex].scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                const prevIndex = (currentIndex - 1 + visibleOptions.length) % visibleOptions.length;
                visibleOptions.forEach(li => li.classList.remove('highlighted'));
                visibleOptions[prevIndex].classList.add('highlighted');
                visibleOptions[prevIndex].scrollIntoView({ block: 'nearest' });
            } else if (e.key === 'Enter' && currentIndex >= 0) {
                e.preventDefault();
                visibleOptions[currentIndex].click();
            }
        });

        // Insert the new elements
        originalSelect.style.display = 'none';
        originalSelect.parentNode.insertBefore(wrapper, originalSelect);
        wrapper.appendChild(input);
        wrapper.appendChild(list);
        wrapper.appendChild(originalSelect);
    }

    document.addEventListener('DOMContentLoaded', function() {
        // Convert existing select elements, excluding multiple selects
        document.querySelectorAll('select:not(.smart-select-converted):not([multiple])').forEach(convertSelectToSmartSelect);

        // Set up MutationObserver to watch for new elements
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1) { // Element node
                        // Check the added node and its children for select elements, excluding multiple selects
                        node.querySelectorAll('select:not(.smart-select-converted):not([multiple])').forEach(convertSelectToSmartSelect);
                    }
                });
            });
        });

        // Start observing the document body for changes
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    });
    </script>
    """) 