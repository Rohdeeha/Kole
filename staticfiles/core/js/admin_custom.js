/**
 * KÓLẸ̀ Situation Room - Dynamic Theme Synchronizer for CKEditor
 * Synchronizes Unfold's Light/Dark mode state to CKEditor iframes in real-time.
 */
(function() {
    function setupCKEditorThemeSync() {
        if (!window.CKEDITOR) {
            setTimeout(setupCKEditorThemeSync, 100);
            return;
        }

        CKEDITOR.on('instanceReady', function(evt) {
            function syncTheme() {
                try {
                    const isDark = document.documentElement.classList.contains('dark');
                    const iframeDoc = evt.editor.document && evt.editor.document.$;
                    if (iframeDoc && iframeDoc.documentElement) {
                        if (isDark) {
                            iframeDoc.documentElement.classList.add('dark');
                        } else {
                            iframeDoc.documentElement.classList.remove('dark');
                        }
                    }
                } catch (e) {
                    // Frame might not be accessible yet
                }
            }

            syncTheme();

            // Observe theme toggling on outer html tag
            const observer = new MutationObserver(syncTheme);
            observer.observe(document.documentElement, { 
                attributes: true, 
                attributeFilter: ['class'] 
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupCKEditorThemeSync);
    } else {
        setupCKEditorThemeSync();
    }
})();
