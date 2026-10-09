module.exports = {
    content: [
        './templates/**/*.html',
        './shop/**/*.py',
        './panel/**/*.py',
        './static/js/**/*.js',
    ],
    theme: {
        extend: {
            colors: {
                cream: '#FBF8F3',
                sand: {
                    DEFAULT: '#FBF8F3',
                    50: '#FBF8F3',
                    100: '#F5EFE4',
                    200: '#E9DFCC',
                    300: '#D9C9AA',
                },
                wood: {
                    DEFAULT: '#A9744F',
                    light: '#D9C9AA',
                    dark: '#1F2421',
                },
                forest: {
                    DEFAULT: '#1B4332',
                    light: '#2F6B4F',
                    dark: '#143225',
                },
                ink: {
                    DEFAULT: '#1F2421',
                    500: '#6B746E',
                    900: '#1F2421',
                },
            },
            fontFamily: {
                sans: ['Inter', 'system-ui', 'sans-serif'],
                display: ['Playfair Display', 'Georgia', 'serif'],
            },
        },
    },
};
