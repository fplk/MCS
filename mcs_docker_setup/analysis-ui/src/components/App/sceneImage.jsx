import React from 'react';

const ImageHolder = ({currentEval, state, imagesBucket, scene}) => {
    const styles = {
      width: '250px',
      height: '250px',
      margin: '5px 25px'
    };

    if(parseInt(currentEval.ground_truth) === 0) {
        styles["border"] = "2px solid red";
    } else {
        styles["border"] = "2px solid white";
    }

    const url = imagesBucket + currentEval["block"] + "/" + currentEval["test"] + "/" + scene + "/scene/scene_" + state.value + ".png"
  
    return (
      <img id={"scene_image_" + scene} className="scene-image" style={styles} src={url} alt=""/>
    );
}

class SceneImage extends React.Component {

    render() {
        
        return (
            <div>
                <div className="scene-info-container">
                    <span className="scene-info-holder"><b>Complexity:</b> {this.props.evals[0].complexity}</span>
                    <span className="scene-info-holder"><b>Occluders:</b> {this.props.evals[0].occluder}</span>
                    <span className="scene-info-holder"><b>Number of Objects:</b> {this.props.evals[0].num_objects}</span>
                    <span className="scene-info-holder-note">(These values are the same across all scenes, and represent the highest value a scene could have)</span>
                </div>
                <div className="scene-image-container">
                    {this.props.evals.map((item, key) =>
                        <div key={"scene_image_" + key}>
                            <div className="sceneinfo">Scene: {key+1}</div>
                            <ImageHolder currentEval={item} state={this.props.state} imagesBucket={this.props.imagesBucket} scene={key+1}/>
                            <div className="sceneScore">Plausibility: {item.plausibility}<br/>Ground Truth: {item.ground_truth}</div>
                        </div>
                    )}
                </div>
            </div>
        );
    }
}

export default SceneImage;