# Change this line to use an absolute import
import streamlit as st
import datetime


def main():
    # Set page config (optional)
    st.set_page_config(
        page_title="Wikipedia Change Viewer",
        layout="wide",  # Use 'wide' to maximize horizontal space
    )

    # -- SIDEBAR: Date Selection + Topics/Articles --
    with st.sidebar:
        st.title("Date Selection")

        # Date interval selection
        st.write("Select a start and end date to see changes during that interval:")
        start_date = st.date_input("Start Date", datetime.date(2021, 1, 1))
        end_date = st.date_input("End Date", datetime.date.today())

        # Topic 1
        st.subheader("Topic 1")
        st.write("- Article 1")
        st.write("- Article 2")

        # Topic 2
        st.subheader("Topic 2")
        st.write("- Article 1")
        st.write("- Article 2")

        # Topic 3
        st.subheader("Topic 3")
        st.write("- Article 1")
        st.write("- Article 2")

    # -- MAIN AREA: Tabs for Wikipedia Articles --
    st.title("Wikipedia Change Highlighter")

    st.write("Use the tabs below to switch between different Wikipedia articles. "
             "Each tab will show the date interval and a space for highlighted text changes.")

    # Create tabs for different Wikipedia articles
    tab1, tab2, tab3 = st.tabs(["Wikipedia Article 1",
                                "Wikipedia Article 2",
                                "Wikipedia Article n"])


    # -- TAB 1 --
    with tab1:
        st.subheader("Date Interval for Wikipedia changes")
        st.write(f"From **{start_date}** to **{end_date}**")

        st.subheader("Wikipedia Text with highlighted changes during Interval")
        st.write("Lorem ipsum... (Here you'd highlight changes for **Wikipedia Article 1**.)")

    # -- TAB 2 --
    with tab2:
        st.subheader("Date Interval for Wikipedia changes")
        st.write(f"From **{start_date}** to **{end_date}**")

        st.subheader("Wikipedia Text with highlighted changes during Interval")
        st.write("Lorem ipsum... (Here you'd highlight changes for **Wikipedia Article 2**.)")

    # -- TAB 3 --
    with tab3:
        st.subheader("Date Interval for Wikipedia changes")
        st.write(f"From **{start_date}** to **{end_date}**")

        st.subheader("Wikipedia Text with highlighted changes during Interval")
        st.write("Lorem ipsum... (Here you'd highlight changes for **Wikipedia Article n**.)")


if __name__ == "__main__":
    main()

