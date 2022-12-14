import React, { Component } from "react";

class PathogenButton extends Component {
  constructor(props) {
    super(props);
    this.state = { selectedOption: "Both" };
  }

  handleOptionChange = changeEvent => {
    this.setState({
      selectedOption: changeEvent.target.value
    });
  };

  handleFormSubmit = formSubmitEvent => {
    formSubmitEvent.preventDefault();

    console.log("You have submitted:", this.state.selectedOption);
  };

    render() {
       return (
        <div className="container">
          <div className="row mt-5">
            <div className="col-sm-12">
              <form onSubmit={this.handleFormSubmit}>

                <div className="form-check">

                    <label> <br/> <b> Pathogenicity </b> <br/> </label>

                  <input type="radio" name="pathogenic" value="Pathogen" id="patho"
                         checked={this.state.selectedOption === "Pathogen"} onChange={this.handleOptionChange}
                         className="form-check-input"/>
                  <label className="form-check-label" htmlFor="patho"> Pathogenic </label>

                </div>

                <div className="form-check">

                  <input type="radio" name="pathogenic" value="No" id="non_patho"
                         checked={this.state.selectedOption === "No"} onChange={this.handleOptionChange}
                         className="form-check-input"/>
                  <label className="form-check-label" htmlFor="non_patho"> Non-Pathogenic </label>

                </div>

                <div className="form-check">

                  <input type="radio" name="pathogenic" value="Both" id="all_patho"
                         checked={this.state.selectedOption==="Both"} onChange={this.handleOptionChange}
                         className="form-check-input" />
                  <label class="form-check-label" for="all_patho"> No Pathogen Filter </label>

                </div>
            </form>
          </div>
        </div>
      </div>
    );
  }
}
export default PathogenButton;