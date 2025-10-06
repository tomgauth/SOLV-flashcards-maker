import genanki


# Stable model IDs: generate once and keep constant
# You can print one via: python -c "import random; print(random.randrange(1<<30, 1<<31))"
RECALL_MODEL_ID = 2000000001
RECOGNIZE_MODEL_ID = 2000000002


def build_recall_model() -> genanki.Model:
    """Return the default 'recall' genanki Model with specified fields/templates/CSS."""
    fields = [
        {"name": "UserLanguage"},
        {"name": "TargetAudio"},
        {"name": "TargetLanguage"},
        {"name": "TargetIPA"},
        {"name": "Notes"},
        {"name": "card_type"},  # kept lowercase to match template placeholder
    ]

    front_template = (
        """
                    <div class="user_language">{{UserLanguage}}</div>
                """
    )

    back_template = (
        """
                    <div class="user_language">{{UserLanguage}}</div>
                    <div style="margin-bottom: 20px;"></div>
                    <div class="target_audio">{{TargetAudio}}</div>
                    <div class="target_language">{{TargetLanguage}}</div>
                    <div class="target_ipa">{{TargetIPA}}</div>
                    <div class="notes">{{Notes}}</div>
                    <div class="notes">{{card_type}}</div>
                    <div class="copyright">©️ SOLV Languages | www.solvlanguages.com</div>
                """
    )

    css_styles = (
        """
@import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;700&display=swap');
.card {
    background-color: #eeebd0;
    color: #0b2027;
    font-family: 'Quicksand', sans-serif;
    text-align: center; /* Centering the text */
    padding: 20px; /* Optional: Adding padding to create space within the card */
}

.user_language {
    color: #373f51;
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 20px; /* Added vertical space */
}

.target_language {
    font-size: 30px;
    font-weight: 700;
    margin-bottom: 20px; /* Added vertical space */
}

.target_audio {
    margin-top: 20px; /* Increased space above the audio */
}

.target_ipa {
    font-size: 22px;
    margin-top: 20px; /* Added vertical space */
}

.notes {
    font-size: 20px;
    margin-top: 20px; /* Increased space between notes and other elements */
}

.copyright {
    font-size: 10px;
    margin-top: 25px; /* Increased space above the copyright */
    color: #00afb9;
}

/* Optional: Center other block elements like audio or images */
.target_audio, .target_ipa, .notes {
    margin: 0 auto; /* Center block elements */
}
        """
    )

    model = genanki.Model(
        RECALL_MODEL_ID,
        "Recall",
        fields=fields,
        templates=[
            {
                "name": "Card 1",
                "qfmt": front_template,
                "afmt": back_template,
            }
        ],
        css=css_styles,
    )

    return model


def build_recognize_model() -> genanki.Model:

    """Return the 'recognize' genanki Model with specified fields/templates/CSS."""
    fields = [
        {"name": "UserLanguage"},
        {"name": "TargetAudio"},
        {"name": "TargetLanguage"},
        {"name": "TargetIPA"},
        {"name": "Notes"},
        {"name": "card_type"},
    ]

    front_template = (
        """
                    <div class="target_audio">{{TargetAudio}}</div>
                """
    )

    back_template = (
        """ 
                    <div class="target_audio">{{TargetAudio}}</div>
                    <div style="margin-bottom: 20px;"></div>
                    <div class="target_language">{{TargetLanguage}}</div>
                    <div class="user_language">{{UserLanguage}}</div>
                    <div class="target_ipa">{{TargetIPA}}</div>
                    <div class="notes">{{Notes}}</div>
                    <div class="notes">{{card_type}}</div>
                    <div class="copyright">©️ SOLV Languages | www.solvlanguages.com</div>
                """
    )

    css_styles = (
        """
@import url('https://fonts.googleapis.com/css2?family=Quicksand:wght@400;700&display=swap');
.card {
    background-color: #eeebd0;
    color: #0b2027;
    font-family: 'Quicksand', sans-serif;
    text-align: center; /* Centering the text */
    padding: 20px; /* Optional: Adding padding to create space within the card */
}

.user_language {
    color: #373f51;
    font-size: 32px;
    font-weight: 700;
    margin-bottom: 20px; /* Added vertical space */
}

.target_language {
    font-size: 30px;
    font-weight: 700;
    margin-bottom: 20px; /* Added vertical space */
}

.target_audio {
    margin-top: 20px; /* Increased space above the audio */
}

.target_ipa {
    font-size: 22px;
    margin-top: 20px; /* Added vertical space */
}

.notes {
    font-size: 20px;
    margin-top: 20px; /* Increased space between notes and other elements */
}

.copyright {
    font-size: 10px;
    margin-top: 25px; /* Increased space above the copyright */
    color: #00afb9;
}

/* Optional: Center other block elements like audio or images */
.target_audio, .target_ipa, .notes {
    margin: 0 auto; /* Center block elements */
}
        """
    )

    model = genanki.Model(
        RECOGNIZE_MODEL_ID,
        "Recognize",
        fields=fields,
        templates=[
            {
                "name": "Card 1",
                "qfmt": front_template,
                "afmt": back_template,
            }
        ],
        css=css_styles,
    )

    return model

